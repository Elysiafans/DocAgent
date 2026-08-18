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


def test_search_finds_relevant_chunk():
    store = _make_store()
    store.upsert_document(42, 1, _chunks())
    hits = store.search("chunk 1", 1, top_k=5)
    assert hits and hits[0].doc_id == 42
    assert hits[0].content == "chunk 1"
    # kb_id 过滤:别的库查不到
    assert store.search("chunk 1", 999, top_k=5) == []


def test_search_hybrid_and_dense_agree_on_top():
    store = _make_store()
    store.upsert_document(42, 1, _chunks())
    hybrid = store.search("chunk 1", 1, top_k=5, hybrid=True)
    dense = store.search("chunk 1", 1, top_k=5, hybrid=False)
    assert hybrid and dense
    assert hybrid[0].content == "chunk 1" == dense[0].content
