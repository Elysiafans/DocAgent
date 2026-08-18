"""A2UI(Agent2User)传输层:结构化 UI 卡片渲染端点。

`POST /a2ui/render` 即时跑 agent 并把回答渲染成卡片;`GET /a2ui/cards/{id}`
把已存消息渲染成卡片(前端回显用)。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Conversation, Message, User
from app.protocols import a2ui
from app.schemas.agent import AgentChatRequest
from app.schemas.ui import A2uiRenderRequest
from app.services import agent_service, chat_service

router = APIRouter(tags=["a2ui"])


def _owned_message(db: Session, user: User, message_id: int) -> Message:
    msg = db.get(Message, message_id)
    conv = db.get(Conversation, msg.conv_id) if msg else None
    if msg is None or conv is None or conv.user_id != user.id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Message not found"
        )
    return msg


@router.post("/a2ui/render")
def render(
    payload: A2uiRenderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    result = agent_service.ask(
        db,
        current_user,
        AgentChatRequest(
            kb_id=payload.kb_id, question=payload.question, route=payload.route
        ),
    )
    msgs = chat_service.list_messages(db, current_user, result.conversation_id)
    assistant = next(m for m in reversed(msgs) if m.role == "assistant")
    return {
        "card": a2ui.render_message_card(assistant, result.sources),
        "conversation_id": result.conversation_id,
        "message_id": assistant.id,
    }


@router.get("/a2ui/cards/{message_id}")
def get_card(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    msg = _owned_message(db, current_user, message_id)
    return a2ui.render_message_card(msg, msg.sources)
