from app.rag.chunking import ChunkRecord
from app.rag.embeddings import fake_embed_texts
from app.rag.reranker import fake_rerank
from app.rag.retrieval import assemble_context, retrieve
from app.rag.vector_store import QdrantVectorStore

TEST_COLLECTION = "docagent_test_collection"


def _store():
    from app.rag.client import get_qdrant

    client = get_qdrant()
    if client.collection_exists(TEST_COLLECTION):
        client.delete_collection(TEST_COLLECTION)
    store = QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=8)
    store.ensure_collection()
    store.upsert_document(
        42,
        1,
        [
            ChunkRecord(
                index=i,
                content=t,
                char_count=len(t),
                hash=f"h{i}",
                meta={"kb_id": 1, "doc_id": 42, "chunk_index": i},
            )
            for i, t in enumerate(["苹果很好吃", "香蕉是黄色的", "西瓜很甜"])
        ],
    )
    return store


def test_retrieve_reranks_and_truncates():
    store = _store()
    chunks = retrieve(store, fake_rerank, "苹果", 1, top_k=10, top_n=2)
    assert len(chunks) <= 2
    assert chunks[0].content == "苹果很好吃"
    assert chunks[0].score >= chunks[1].score


def test_retrieve_threshold_filters():
    store = _store()
    all_hits = retrieve(store, fake_rerank, "苹果", 1, top_k=10, top_n=5, threshold=0.0)
    assert len(all_hits) >= 1
    # 高阈值 -> 全部丢弃
    strict = retrieve(store, fake_rerank, "苹果", 1, top_k=10, top_n=5, threshold=10.0)
    assert strict == []


def test_retrieve_empty_kb():
    store = _store()
    assert retrieve(store, fake_rerank, "苹果", 999, top_k=5) == []


def test_assemble_context_numbers_and_names():
    from types import SimpleNamespace

    chunks = [
        SimpleNamespace(doc_id=1, doc_name="a.md", chunk_index=0, content="内容一"),
        SimpleNamespace(doc_id=2, doc_name="b.md", chunk_index=3, content="内容二"),
    ]
    ctx = assemble_context(chunks, {1: "a.md", 2: "b.md"})
    assert "[1]" in ctx and "a.md" in ctx
    assert "[2]" in ctx and "b.md" in ctx
