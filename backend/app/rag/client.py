from functools import lru_cache

from qdrant_client import QdrantClient

from app.core.config import get_settings


@lru_cache
def get_qdrant() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.QDRANT_URL)
