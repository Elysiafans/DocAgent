from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    kind: str = Field(default="note", max_length=20)
    conv_id: int | None = None


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    content: str
    meta: dict[str, Any] | None
    created_at: datetime
