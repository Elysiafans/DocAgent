"""A2A 传输层:`POST /a2a`(JSON-RPC 2.0)。

adapter 负责把 A2A 方法映射到 DocAgent 业务:消息 → `agent_service.ask`
(跑 Supervisor + 4 agent),任务 → `task_runs` 可观测记录。
"""
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.protocols import skills
from app.protocols.a2a import A2aError, A2aServer
from app.protocols.jsonrpc import INVALID_PARAMS
from app.schemas.agent import AgentChatRequest
from app.services import agent_service

router = APIRouter(tags=["a2a"])

# 内部 TaskRun 状态 → A2A 规范任务状态
_A2A_STATUS = {"success": "completed", "failed": "failed", "running": "working"}


class _Adapter:
    def __init__(self, db: Session, user: User):
        self._db = db
        self._user = user

    def agent_card(self) -> dict:
        return {
            "name": "docagent",
            "description": (
                "DocAgent 多智能体知识库问答平台:接收文本消息,经 Supervisor "
                "路由到 RAG/总结/对比/工具智能体作答。"
            ),
            "url": "/a2a",
            "version": "0.1.0",
            "capabilities": {"streaming": False, "pushNotifications": False},
            "skills": [s["name"] for s in skills.list_skills()],
        }

    def ask(self, params: dict) -> dict:
        metadata = params.get("metadata") or {}
        kb_id = metadata.get("kb_id")
        if not kb_id:
            raise A2aError(INVALID_PARAMS, "metadata.kb_id is required")
        parts = params.get("message", {}).get("parts") or []
        text = next(
            (
                p.get("text")
                for p in parts
                if p.get("kind") == "text" and p.get("text")
            ),
            None,
        )
        if not text:
            raise A2aError(INVALID_PARAMS, "message.parts[].text is required")

        payload = AgentChatRequest(
            kb_id=int(kb_id), question=text, route=metadata.get("route")
        )
        result = agent_service.ask(self._db, self._user, payload)
        return {
            "taskId": str(result.run_id),
            "status": "completed",
            "message": {
                "messageId": str(result.run_id),
                "conversationId": result.conversation_id,
                "taskId": str(result.run_id),
                "role": "agent",
                "parts": [{"kind": "text", "text": result.answer}],
            },
            "artifacts": [
                {
                    "name": "sources",
                    "parts": [
                        {
                            "kind": "text",
                            "text": json.dumps(result.sources, ensure_ascii=False),
                        }
                    ],
                }
            ],
        }

    def get_task(self, params: dict) -> dict:
        task_id = params.get("id")
        if not task_id:
            raise A2aError(INVALID_PARAMS, "id is required")
        run = agent_service.get_task_run(self._db, self._user, int(task_id))
        return {
            "id": str(run.id),
            "status": _A2A_STATUS.get(run.status, run.status),
            "error": run.error,
        }


@router.post("/a2a")
def a2a_endpoint(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return A2aServer(_Adapter(db, current_user)).handle(payload)
