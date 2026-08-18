"""检索流水线:混合检索 + RRF -> 重排 -> 阈值过滤 -> 编号上下文组装。"""

from dataclasses import dataclass, field
from typing import Any

from app.rag.reranker import Reranker
from app.rag.vector_store import QdrantVectorStore


@dataclass
class RetrievedChunk:
    doc_id: int
    chunk_index: int
    content: str
    score: float
    meta: dict[str, Any] = field(default_factory=dict)
    doc_name: str | None = None


def retrieve(
    store: QdrantVectorStore,
    reranker: Reranker | None,
    query: str,
    kb_id: int,
    top_k: int = 20,
    top_n: int = 5,
    hybrid: bool = True,
    threshold: float | None = None,
) -> list[RetrievedChunk]:
    """检索流水线:search(混合+RRF)-> rerank(top_k->top_n)-> 阈值过滤。"""
    hits = store.search(query, kb_id, top_k=top_k, hybrid=hybrid)
    if not hits:
        return []
    if reranker is not None:
        ranked = reranker(query, [h.content for h in hits], top_n)
        chunks = [
            RetrievedChunk(
                doc_id=hits[i].doc_id,
                chunk_index=hits[i].chunk_index,
                content=hits[i].content,
                score=score,
                meta=hits[i].meta,
            )
            for i, score in ranked
        ]
    else:
        chunks = [
            RetrievedChunk(
                doc_id=h.doc_id,
                chunk_index=h.chunk_index,
                content=h.content,
                score=h.score,
                meta=h.meta,
            )
            for h in hits[:top_n]
        ]
    if threshold is not None:
        chunks = [c for c in chunks if c.score >= threshold]
    return chunks


def assemble_context(chunks: list[RetrievedChunk], doc_names: dict[int, str]) -> str:
    """把命中块编成带 [编号] 的上下文,供 prompt 使用并强制 LLM 按编号引用。"""
    lines = []
    for i, c in enumerate(chunks, 1):
        name = doc_names.get(c.doc_id, f"文档{c.doc_id}")
        lines.append(f"[{i}] {c.content} (来源:{name} 第{c.chunk_index + 1}块)")
    return "\n".join(lines)
