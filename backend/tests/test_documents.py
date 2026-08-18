import app.services.ingestion_service as ing
from app.rag.embeddings import fake_embed_texts
from app.rag.vector_store import QdrantVectorStore

TEST_COLLECTION = "docagent_test_collection"
_FILES = {"text/plain": ("sample.txt", "第一行。\n第二行。\n第三行。".encode())}


def _auth(client, email="d@test.com"):
    client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password123"}
    )
    r = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _store():
    store = QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=8)
    store.ensure_collection()
    return store


def test_upload_process_and_query_document(client, monkeypatch):
    # 注入 fake 嵌入到 ingestion_service,避免真实 SiliconFlow 调用
    monkeypatch.setattr(
        ing,
        "_make_vector_store",
        lambda kb_id: QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=8),
    )

    h = _auth(client)
    kb_id = client.post(
        "/api/v1/knowledge_bases", json={"name": "库A"}, headers=h
    ).json()["id"]

    r = client.post(
        f"/api/v1/knowledge_bases/{kb_id}/documents",
        files={"file": _FILES["text/plain"]},
        headers=h,
    )
    assert r.status_code == 201
    doc_id = r.json()["id"]

    # 后台摄取在 TestClient 里同步执行 -> 状态应为 ready
    doc = client.get(f"/api/v1/documents/{doc_id}", headers=h).json()
    assert doc["status"] == "ready"
    assert doc["chunk_count"] >= 1

    store = _store()
    assert store.count_chunks(doc_id) == doc["chunk_count"]

    docs = client.get(f"/api/v1/knowledge_bases/{kb_id}/documents", headers=h).json()
    assert any(d["id"] == doc_id for d in docs)

    assert client.delete(f"/api/v1/documents/{doc_id}", headers=h).status_code == 204
    assert store.count_chunks(doc_id) == 0


def test_upload_requires_kb_ownership(client):
    h = _auth(client)
    r = client.post(
        "/api/v1/knowledge_bases/999/documents",
        files={"file": _FILES["text/plain"]},
        headers=h,
    )
    assert r.status_code == 404


def test_documents_require_auth(client):
    assert client.get("/api/v1/knowledge_bases/1/documents").status_code == 401
