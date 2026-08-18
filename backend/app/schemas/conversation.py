from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kb_id: int
    title: str
    created_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conv_id: int
    role: str
    content: str
    sources: list[dict[str, Any]] | None
    created_at: datetime
