import app.services.chat_service as chat_svc
import app.services.ingestion_service as ing
from app.rag.chat_provider import ChatProvider
from app.rag.embeddings import fake_embed_texts
from app.rag.reranker import fake_rerank
from app.rag.vector_store import QdrantVectorStore

TEST_COLLECTION = "docagent_test_collection"
DOC_BYTES = "DocAgent 是多智能体知识库问答平台,支持 RAG 检索。".encode()


class FakeChat(ChatProvider):
    def complete(self, messages, temperature=None):
        assert any(m["role"] == "system" for m in messages)
        return "答案是[1]:多智能体知识库。详见资料[1]。"


def _make_fake_store():
    from app.rag.client import get_qdrant

    client = get_qdrant()
    if client.collection_exists(TEST_COLLECTION):
        client.delete_collection(TEST_COLLECTION)
    return QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=8)


def _patch_providers(monkeypatch):
    store = _make_fake_store()
    monkeypatch.setattr(ing, "_make_vector_store", lambda kb_id: store)
    monkeypatch.setattr(chat_svc, "_make_vector_store", lambda kb_id: store)
    monkeypatch.setattr(chat_svc, "_make_reranker", lambda: fake_rerank)
    monkeypatch.setattr(chat_svc, "_make_chat_provider", FakeChat)


def _setup(client, email="c@test.com"):
    client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password123"}
    )
    tok = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    kb_id = client.post(
        "/api/v1/knowledge_bases", json={"name": "聊天库"}, headers=h
    ).json()["id"]
    client.post(
        f"/api/v1/knowledge_bases/{kb_id}/documents",
        files={"file": ("r.md", DOC_BYTES)},
        headers=h,
    )
    return h, kb_id


def test_chat_end_to_end(client, monkeypatch):
    _patch_providers(monkeypatch)
    h, kb_id = _setup(client)
    r = client.post(
        "/api/v1/chat", json={"kb_id": kb_id, "question": "什么是多智能体?"}, headers=h
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["answer"] and "[1]" in data["answer"]
    assert len(data["sources"]) >= 1
    assert data["sources"][0]["doc_name"] == "r.md"
    conv_id = data["conversation_id"]

    # 多轮:复用 conversation_id,带历史
    r2 = client.post(
        "/api/v1/chat",
        json={"kb_id": kb_id, "question": "RAG 是什么?", "conversation_id": conv_id},
        headers=h,
    )
    assert r2.status_code == 200

    # 会话与消息已持久化
    convs = client.get("/api/v1/conversations", headers=h).json()
    assert any(c["id"] == conv_id for c in convs)
    msgs = client.get(f"/api/v1/conversations/{conv_id}/messages", headers=h).json()
    assert len(msgs) == 4  # 两轮 × (user+assistant)
    assert msgs[1]["sources"] and msgs[1]["sources"][0]["doc_name"] == "r.md"


def test_chat_requires_owned_kb(client, monkeypatch):
    _patch_providers(monkeypatch)
    h, _ = _setup(client)
    r = client.post("/api/v1/chat", json={"kb_id": 999, "question": "hi"}, headers=h)
    assert r.status_code == 404


def test_chat_requires_auth(client):
    assert (
        client.post("/api/v1/chat", json={"kb_id": 1, "question": "hi"}).status_code
        == 401
    )
