from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentChatRequest(BaseModel):
    kb_id: int
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None
    route: str | None = Field(
        default=None, pattern="^(rag|summary|compare|utility)$"
    )


class TaskRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    status: str
    error: str | None
    trace: dict[str, Any] | None
    started_at: datetime
    finished_at: datetime | None
