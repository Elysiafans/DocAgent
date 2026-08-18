"""MCP streamable HTTP 传输层:`POST /mcp`(JSON 或 SSE)。

协议逻辑见 `app.protocols.mcp_server.McpServer`;此处负责鉴权、知识库归属校验、
按 Accept 头选择 JSON / SSE 编码。
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.agents.tools import AgentContext
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import KnowledgeBase, User
from app.protocols.mcp_server import McpServer
from app.protocols.mcp_tools import mcp_tool_specs
from app.services import agent_service

router = APIRouter(tags=["mcp"])


def _get_owned_kb(db: Session, user: User, kb_id: int) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None or kb.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    return kb


def _make_ctx_factory(db: Session, user: User):
    """按 kb_id 构造 AgentContext(含归属校验 + 真实 Provider 工厂)。"""

    def ctx_factory(kb_id: int) -> AgentContext:
        kb = _get_owned_kb(db, user, kb_id)
        return AgentContext(
            db=db,
            user=user,
            kb=kb,
            store_factory=agent_service._make_vector_store,
            reranker_factory=agent_service._make_reranker,
        )

    return ctx_factory


@router.post("/mcp")
async def mcp_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001  body 非 JSON
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
        )

    server = McpServer(mcp_tool_specs(), _make_ctx_factory(db, current_user))
    resp = server.handle(payload)

    if "text/event-stream" in request.headers.get("accept", ""):
        def gen():
            yield f"event: message\ndata: {json.dumps(resp, ensure_ascii=False)}\n\n"
            # streamable HTTP 终止帧
            yield 'event: message\ndata: {"jsonrpc":"2.0","result":{"_meta":{}},"id":null}\n\n'

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return JSONResponse(resp)
