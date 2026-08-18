from pydantic import BaseModel, Field


class A2uiRenderRequest(BaseModel):
    kb_id: int
    question: str = Field(min_length=1, max_length=4000)
    route: str | None = Field(
        default=None, pattern="^(rag|summary|compare|utility)$"
    )
