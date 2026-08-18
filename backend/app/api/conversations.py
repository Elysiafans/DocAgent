from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.conversation import ConversationOut, MessageOut
from app.services import chat_service

router = APIRouter(tags=["conversations"])


@router.get("/conversations", response_model=list[ConversationOut])
def list_convs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConversationOut]:
    return chat_service.list_conversations(db, current_user)


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
def list_msgs(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MessageOut]:
    return chat_service.list_messages(db, current_user, conv_id)
