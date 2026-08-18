from typing import Callable

from qdrant_client import models

from app.core.config import get_settings
from app.rag.chunking import ChunkRecord
from app.rag.client import get_qdrant

Embedder = Callable[[list[str]], list[list[float]]]


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
        for c, vec in zip(chunks, vectors):
            # 稀疏向量:演示级词袋(按空格/标点切分),D4 打磨
            tokens: dict[str, int] = {}
            for tok in c.content.replace("。", " ").replace(",", " ").split():
                tokens[tok] = tokens.get(tok, 0) + 1
            points.append(
                models.PointStruct(
                    id=self._point_id(doc_id, c.index),
                    vector={
                        "dense": vec,
                        "sparse": models.SparseVector(
                            indices=[hash(t) & 0xFFFFFFFF for t in tokens],
                            values=[float(v) for v in tokens.values()],
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

    @staticmethod
    def _point_id(doc_id: int, index: int) -> int:
        return doc_id * 10_000 + index
