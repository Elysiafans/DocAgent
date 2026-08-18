from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Document, KnowledgeBase
from app.rag.chunking import chunk_document
from app.rag.embeddings import SiliconFlowEmbeddingProvider
from app.rag.parsers import parse_document
from app.rag.vector_store import QdrantVectorStore


def _make_vector_store(kb_id: int) -> QdrantVectorStore:
    """生产用真实 SiliconFlow 嵌入 + 生产 collection。测试 monkeypatch 替换。"""
    return QdrantVectorStore(
        get_settings().QDRANT_COLLECTION, SiliconFlowEmbeddingProvider()
    )


def ingest_document(db: Session, doc: Document, raw: bytes) -> None:
    """后台任务:parse -> chunk -> embed -> upsert -> 更新 Document。"""
    kb = db.get(KnowledgeBase, doc.kb_id)
    store = _make_vector_store(kb.id)

    try:
        db.refresh(doc)
        doc.status = "parsing"
        doc.stage = "parse"
        db.commit()

        pages = parse_document(raw, doc.file_type)
        text = "\n".join(p.text for p in pages if p.text.strip())

        doc.status = "chunking"
        doc.stage = "chunk"
        doc.progress = 40
        db.commit()
        chunks = chunk_document(
            text,
            kb.chunk_strategy,
            kb.chunk_size,
            kb.chunk_overlap,
            source={"kb_id": kb.id, "doc_id": doc.id},
        )
        if not chunks:
            raise ValueError("文档解析后无可分块内容")

        doc.status = "embedding"
        doc.stage = "embed"
        doc.progress = 70
        db.commit()
        n = store.upsert_document(doc.id, kb.id, chunks)

        doc.status = "ready"
        doc.stage = "done"
        doc.progress = 100
        doc.chunk_count = n
        doc.error = None
        db.commit()
    except Exception as e:
        db.rollback()
        doc.status = "failed"
        doc.error = str(e)
        db.commit()
