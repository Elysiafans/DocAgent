import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.agent import AgentChatRequest, TaskRunOut
from app.services import agent_service

router = APIRouter(tags=["agent_chat"])


def _sse(gen) -> StreamingResponse:
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/agent")
def chat_agent(
    payload: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """多智能体对话:SSE 流式(route/node/token/tool/answer/sources/done/error)。"""
    prepared = agent_service.prepare_agent_chat(db, current_user, payload)

    def gen():
        # SSE 帧化:service 产出结构化事件 dict,trace 记录;这里编码为 data: 行
        for ev in agent_service.stream_agent_chat(
            db, current_user, payload, prepared
        ):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return _sse(gen())


@router.get("/task_runs", response_model=list[TaskRunOut])
def list_task_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TaskRunOut]:
    return agent_service.list_task_runs(db, current_user)


@router.get("/task_runs/{run_id}", response_model=TaskRunOut)
def get_task_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskRunOut:
    return agent_service.get_task_run(db, current_user, run_id)
