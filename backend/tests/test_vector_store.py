from app.rag.chunking import ChunkRecord
from app.rag.client import get_qdrant
from app.rag.embeddings import fake_embed_texts
from app.rag.vector_store import QdrantVectorStore

TEST_COLLECTION = "docagent_test_collection"


def _make_store(dim=8) -> QdrantVectorStore:
    client = get_qdrant()
    if client.collection_exists(TEST_COLLECTION):
        client.delete_collection(TEST_COLLECTION)
    store = QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=dim)
    store.ensure_collection()
    return store


def _chunks(n=3):
    return [
        ChunkRecord(
            index=i,
            content=f"chunk {i}",
            char_count=6,
            hash=f"h{i}",
            meta={"kb_id": 1, "doc_id": 42, "chunk_index": i},
        )
        for i in range(n)
    ]


def test_upsert_and_count():
    store = _make_store()
    n = store.upsert_document(42, 1, _chunks())
    assert n == 3
    assert store.count_chunks(42) == 3


def test_delete_document_chunks():
    store = _make_store()
    store.upsert_document(42, 1, _chunks())
    store.delete_document_chunks(42)
    assert store.count_chunks(42) == 0


def test_ensure_collection_idempotent():
    store = _make_store()
    store.ensure_collection()  # 第二次调用不报错
    assert get_qdrant().collection_exists(TEST_COLLECTION)
