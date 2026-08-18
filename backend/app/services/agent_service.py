from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generator

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import graph as agent_graph
from app.agents.llm import get_chat_llm
from app.agents.routes import ROUTES
from app.agents.tools import AgentContext, build_tools
from app.core.config import get_settings
from app.models import Conversation, KnowledgeBase, Message, TaskRun, User
from app.rag.embeddings import SiliconFlowEmbeddingProvider
from app.rag.reranker import Reranker, SiliconFlowReranker
from app.rag.vector_store import QdrantVectorStore
from app.schemas.agent import AgentChatRequest


# ---- Provider 注入缝(测试 monkeypatch 替换)----
def _make_vector_store(kb_id: int) -> QdrantVectorStore:
    return QdrantVectorStore(
        get_settings().QDRANT_COLLECTION, SiliconFlowEmbeddingProvider()
    )


def _make_reranker() -> Reranker | None:
    return SiliconFlowReranker()


def _make_chat_llm():
    return get_chat_llm()


def _get_owned_kb(db: Session, user: User, kb_id: int) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None or kb.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    return kb


def _get_owned_conversation(db: Session, user: User, conv_id: int) -> Conversation:
    conv = db.get(Conversation, conv_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return conv


@dataclass
class PreparedRun:
    """流式前一次性准备好的依赖:校验/会话已就绪,可抛 HTTPException。"""

    conv: Conversation
    ctx: AgentContext
    tools_by_agent: dict[str, list]
    llm: Any
    thread_id: str


def prepare_agent_chat(
    db: Session, user: User, payload: AgentChatRequest
) -> PreparedRun:
    """同步阶段:校验 KB/会话归属,构造上下文与图依赖(错误返回正常状态码)。"""
    kb = _get_owned_kb(db, user, payload.kb_id)
    if payload.conversation_id:
        conv = _get_owned_conversation(db, user, payload.conversation_id)
        if conv.kb_id != kb.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Conversation belongs to another knowledge base",
            )
    else:
        conv = Conversation(user_id=user.id, kb_id=kb.id, title=payload.question[:30])
        db.add(conv)
        db.commit()
        db.refresh(conv)

    ctx = AgentContext(
        db=db,
        user=user,
        kb=kb,
        store_factory=_make_vector_store,
        reranker_factory=_make_reranker,
    )
    tools_by_agent = {name: build_tools(ctx) for name in ROUTES}
    return PreparedRun(
        conv=conv,
        ctx=ctx,
        tools_by_agent=tools_by_agent,
        llm=_make_chat_llm(),
        thread_id=f"conv_{conv.id}",  # InMemorySaver 会话记忆:按会话分线程
    )


def stream_agent_chat(
    db: Session,
    user: User,
    payload: AgentChatRequest,
    prepared: PreparedRun,
) -> Generator[dict[str, Any], None, None]:
    """流式阶段:跑 Supervisor+4 agent 图,逐事件 yield,并做会话/任务持久化。"""
    run_row = TaskRun(
        user_id=user.id,
        conv_id=prepared.conv.id,
        type="agent",
        status="running",
        trace={"route": payload.route, "events": []},
    )
    db.add(run_row)
    db.commit()
    db.refresh(run_row)

    graph = agent_graph.build_graph(prepared.llm, prepared.tools_by_agent)
    answer_parts: list[str] = []
    final_answer = ""
    route = payload.route

    try:
        for ev in agent_graph.run(
            graph, payload.question, prepared.thread_id, payload.route
        ):
            etype = ev["type"]
            if etype == "token":
                answer_parts.append(ev["content"])
            elif etype == "answer":
                final_answer = ev["content"]
            elif etype == "route":
                route = ev["route"]

            trace = dict(run_row.trace or {})
            trace["events"] = trace.get("events", []) + [ev]
            run_row.trace = trace
            db.add(run_row)
            db.commit()  # 增量提交:流式中途即可观测 trace
            yield ev

        answer = final_answer or "".join(answer_parts)
        sources = prepared.ctx.collected_sources

        db.add(Message(conv_id=prepared.conv.id, role="user", content=payload.question))
        db.add(
            Message(
                conv_id=prepared.conv.id,
                role="assistant",
                content=answer,
                sources=sources or None,
                agent_type=f"agent:{route or 'auto'}",
            )
        )
        run_row.status = "success"
        run_row.finished_at = datetime.now(timezone.utc)
        db.commit()

        yield {"type": "sources", "sources": sources}
        yield {
            "type": "done",
            "conversation_id": prepared.conv.id,
            "run_id": run_row.id,
            "answer": answer,
        }
    except Exception as e:  # noqa: BLE001
        db.rollback()
        run_row.status = "failed"
        run_row.error = f"{type(e).__name__}: {e}"
        run_row.finished_at = datetime.now(timezone.utc)
        db.commit()
        yield {"type": "error", "message": str(e)}


def list_task_runs(db: Session, user: User) -> list[TaskRun]:
    return list(
        db.execute(
            select(TaskRun)
            .where(TaskRun.user_id == user.id)
            .order_by(TaskRun.id.desc())
        ).scalars()
    )


def get_task_run(db: Session, user: User, run_id: int) -> TaskRun:
    run = db.get(TaskRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task run not found")
    return run
