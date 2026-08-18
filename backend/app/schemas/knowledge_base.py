from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChunkStrategy = Literal["recursive", "markdown_header"]


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    chunk_strategy: ChunkStrategy = "recursive"
    chunk_size: int = Field(default=800, ge=100, le=2000)
    chunk_overlap: int = Field(default=100, ge=0, le=500)


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    chunk_strategy: ChunkStrategy | None = None
    chunk_size: int | None = Field(default=None, ge=100, le=2000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=500)


class KnowledgeBaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    owner_id: int
    chunk_strategy: str
    chunk_size: int
    chunk_overlap: int
    created_at: datetime
