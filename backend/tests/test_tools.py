import app.agents.tools as tools_mod
from app.agents.tools import AgentContext, build_tools
from app.rag.chunking import ChunkRecord
from app.rag.embeddings import fake_embed_texts
from app.rag.vector_store import QdrantVectorStore

TEST_COLLECTION = "docagent_test_collection"


def _ctx():
    from app.rag.client import get_qdrant

    client = get_qdrant()
    if client.collection_exists(TEST_COLLECTION):
        client.delete_collection(TEST_COLLECTION)
    store = QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=8)
    store.ensure_collection()
    store.upsert_document(
        7,
        1,
        [
            ChunkRecord(
                index=i,
                content=t,
                char_count=len(t),
                hash=f"h{i}",
                meta={"kb_id": 1, "doc_id": 7, "chunk_index": i},
            )
            for i, t in enumerate(["DocAgent 支持 PDF 解析", "DocAgent 支持 Word 解析"])
        ],
    )
    return AgentContext(
        db=None,
        user=None,
        kb=type("KB", (), {"id": 1})(),
        store_factory=lambda kb_id: store,
        reranker_factory=None,
    )


def _tools(ctx):
    return {t.name: t for t in build_tools(ctx)}


def test_knowledge_search_formats_and_collects_sources():
    ctx = _ctx()
    tools = _tools(ctx)
    out = tools["knowledge_search"].invoke({"query": "DocAgent 支持", "top_k": 5})
    assert "[1]" in out and "DocAgent" in out
    assert ctx.collected_sources and ctx.collected_sources[0]["doc_id"] == 7


def test_calculator_safe_arith():
    ctx = _ctx()
    tools = _tools(ctx)
    assert tools["calculator"].invoke({"expr": "(1 + 2) * 3"}) == "9"
    assert tools["calculator"].invoke({"expr": "10 / 4"}) == "2.5"


def test_calculator_rejects_unsafe():
    ctx = _ctx()
    tools = _tools(ctx)
    out = tools["calculator"].invoke({"expr": "__import__('os').system('x')"})
    assert "不支持" in out  # 安全拒绝


def test_web_search_uses_impl(monkeypatch):
    def fake_impl(q):
        return "DDG: result1 / result2"

    monkeypatch.setattr(tools_mod, "_web_search_impl", fake_impl)
    ctx = _ctx()
    tools = _tools(ctx)
    assert "result1" in tools["web_search"].invoke({"query": "python"})


def test_compare_documents_multi_topic():
    ctx = _ctx()
    tools = _tools(ctx)
    out = tools["compare_documents"].invoke(
        {"query": "DocAgent", "topics": ["PDF", "Word"]}
    )
    assert "[1]" in out and "DocAgent" in out
