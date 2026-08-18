from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kb_id: int
    name: str
    file_type: str
    size: int
    status: str  # uploading / parsing / chunking / embedding / ready / failed
    progress: int
    stage: str
    chunk_count: int
    error: str | None
    created_at: datetime
