from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    kb_id: int
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None
    top_k: int = Field(default=20, ge=5, le=100)
    top_n: int = Field(default=5, ge=1, le=20)
    hybrid: bool = True
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class ChatSource(BaseModel):
    doc_id: int
    doc_name: str | None
    chunk_index: int
    content: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    conversation_id: int
