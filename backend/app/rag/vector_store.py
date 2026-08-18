from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from qdrant_client import models

from app.core.config import get_settings
from app.rag.chunking import ChunkRecord
from app.rag.client import get_qdrant
from app.rag.sparse import build_sparse_vector

Embedder = Callable[[list[str]], list[list[float]]]


@dataclass
class SearchHit:
    doc_id: int
    chunk_index: int
    content: str
    score: float
    meta: dict[str, Any]


class QdrantVectorStore:
    """QDrant 读写封装:稠密(bge-m3)+ 稀疏(BM25)同 collection。"""

    def __init__(self, collection: str, embedder: Embedder, dim: int | None = None):
        self.collection = collection
        self.embedder = embedder
        self.dim = dim or get_settings().EMBEDDING_MODEL_DIM
        self._client = get_qdrant()

    def ensure_collection(self) -> None:
        if self._client.collection_exists(self.collection):
            return
        self._client.create_collection(
            collection_name=self.collection,
            vectors_config={
                "dense": models.VectorParams(
                    size=self.dim, distance=models.Distance.COSINE
                )
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(
                    modifier=models.Modifier.IDF  # BM25 稀疏权重
                )
            },
        )

    def upsert_document(self, doc_id: int, kb_id: int, chunks: list[ChunkRecord]) -> int:
        self.ensure_collection()
        texts = [c.content for c in chunks]
        vectors = self.embedder(texts)
        points = []
        for c, vec in zip(chunks, vectors, strict=False):
            indices, values = build_sparse_vector(c.content)
            points.append(
                models.PointStruct(
                    id=self._point_id(doc_id, c.index),
                    vector={
                        "dense": vec,
                        "sparse": models.SparseVector(
                            indices=indices, values=values
                        ),
                    },
                    payload={
                        "kb_id": kb_id,
                        "doc_id": doc_id,
                        "chunk_index": c.index,
                        "content": c.content,
                        "char_count": c.char_count,
                        "hash": c.hash,
                        **c.meta,
                    },
                )
            )
        self._client.upsert(collection_name=self.collection, points=points)
        return len(points)

    def delete_document_chunks(self, doc_id: int) -> None:
        self._client.delete(
            collection_name=self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="doc_id", match=models.MatchValue(value=doc_id)
                        )
                    ]
                )
            ),
        )

    def count_chunks(self, doc_id: int) -> int:
        return self._client.count(
            collection_name=self.collection,
            count_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="doc_id", match=models.MatchValue(value=doc_id)
                    )
                ]
            ),
            exact=True,
        ).count

    def search(
        self, query_text: str, kb_id: int, top_k: int = 20, hybrid: bool = True
    ) -> list[SearchHit]:
        """混合检索:稠密(bge-m3)+ 稀疏(BM25)prefetch,原生 RRF 融合,按 kb_id 过滤。"""
        self.ensure_collection()
        dense = self.embedder([query_text])[0]
        kb_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="kb_id", match=models.MatchValue(value=kb_id)
                )
            ]
        )
        if hybrid:
            s_idx, s_vals = build_sparse_vector(query_text)
            prefetch = [
                models.Prefetch(
                    query=dense, using="dense", limit=top_k, filter=kb_filter
                )
            ]
            if s_idx:
                prefetch.append(
                    models.Prefetch(
                        query=models.SparseVector(indices=s_idx, values=s_vals),
                        using="sparse",
                        limit=top_k,
                        filter=kb_filter,
                    )
                )
            resp = self._client.query_points(
                collection_name=self.collection,
                prefetch=prefetch,
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=top_k,
                with_payload=True,
            )
        else:
            resp = self._client.query_points(
                collection_name=self.collection,
                query=dense,
                using="dense",
                query_filter=kb_filter,
                limit=top_k,
                with_payload=True,
            )
        hits: list[SearchHit] = []
        for p in resp.points:
            pl = p.payload or {}
            hits.append(
                SearchHit(
                    doc_id=pl["doc_id"],
                    chunk_index=pl["chunk_index"],
                    content=pl["content"],
                    score=float(p.score),
                    meta=pl,
                )
            )
        return hits

    @staticmethod
    def _point_id(doc_id: int, index: int) -> int:
        return doc_id * 10_000 + index
