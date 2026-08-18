
import app.services.agent_service as agent_svc
import app.services.ingestion_service as ing
from app.rag.embeddings import fake_embed_texts
from app.rag.vector_store import QdrantVectorStore
from langchain_core.messages import AIMessage

from tests.fake_model import FakeToolCallingModel

TEST_COLLECTION = "docagent_test_collection"
DOC_BYTES = "DocAgent 是多智能体知识库问答平台,支持 RAG 检索。".encode()


def _patch(monkeypatch):
    from app.rag.client import get_qdrant

    client = get_qdrant()
    if client.collection_exists(TEST_COLLECTION):
        client.delete_collection(TEST_COLLECTION)
    store = QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=8)
    store.ensure_collection()
    monkeypatch.setattr(ing, "_make_vector_store", lambda kb_id: store)
    monkeypatch.setattr(agent_svc, "_make_vector_store", lambda kb_id: store)
    monkeypatch.setattr(agent_svc, "_make_reranker", lambda: None)

    llm = FakeToolCallingModel(
        [
            AIMessage(content="rag"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "knowledge_search",
                        "args": {"query": "多智能体"},
                        "id": "call_1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="DocAgent 是[1]多智能体知识库问答平台。"),
        ]
    )
    monkeypatch.setattr(agent_svc, "_make_chat_llm", lambda: llm)
    return llm


def _setup(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "a7@test.com", "password": "password123"},
    )
    tok = client.post(
        "/api/v1/auth/login",
        json={"email": "a7@test.com", "password": "password123"},
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    kb_id = client.post(
        "/api/v1/knowledge_bases", json={"name": "a2a库"}, headers=h
    ).json()["id"]
    client.post(
        f"/api/v1/knowledge_bases/{kb_id}/documents",
        files={"file": ("r.md", DOC_BYTES)},
        headers=h,
    )
    return h, kb_id


def _msg_send(kb_id, text="什么是多智能体?"):
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {
            "message": {"parts": [{"kind": "text", "text": text}]},
            "metadata": {"kb_id": kb_id},
        },
    }


def test_a2a_agent_get(client):
    h, _ = _setup(client)
    resp = client.post(
        "/a2a",
        json={"jsonrpc": "2.0", "id": 1, "method": "agent/get", "params": {}},
        headers=h,
    )
    assert resp.status_code == 200
    card = resp.json()["result"]
    assert card["name"] == "docagent"
    assert card["description"]
    assert "rag_qa" in card["skills"]


def test_a2a_message_send(client, monkeypatch):
    _patch(monkeypatch)
    h, kb_id = _setup(client)
    resp = client.post("/a2a", json=_msg_send(kb_id), headers=h)
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["status"] == "completed"
    assert result["taskId"]
    text = result["message"]["parts"][0]["text"]
    assert "DocAgent" in text

    # 会话与任务已持久化
    convs = client.get("/api/v1/conversations", headers=h).json()
    assert any(c["id"] == result["message"]["conversationId"] for c in convs)
    runs = client.get("/api/v1/task_runs", headers=h).json()
    assert any(r["type"] == "agent" and r["status"] == "success" for r in runs)


def test_a2a_tasks_get(client, monkeypatch):
    _patch(monkeypatch)
    h, kb_id = _setup(client)
    task_id = client.post("/a2a", json=_msg_send(kb_id), headers=h).json()[
        "result"
    ]["taskId"]
    resp = client.post(
        "/a2a",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tasks/get",
            "params": {"id": task_id},
        },
        headers=h,
    )
    assert resp.json()["result"]["status"] == "completed"


def test_a2a_unknown_method(client):
    h, _ = _setup(client)
    resp = client.post(
        "/a2a",
        json={"jsonrpc": "2.0", "id": 3, "method": "nope", "params": {}},
        headers=h,
    )
    assert resp.json()["error"]["code"] == -32601


def test_a2a_missing_kb_metadata(client, monkeypatch):
    _patch(monkeypatch)
    h, _ = _setup(client)
    resp = client.post(
        "/a2a",
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "message/send",
            "params": {
                "message": {"parts": [{"kind": "text", "text": "hi"}]},
                "metadata": {},
            },
        },
        headers=h,
    )
    assert resp.json()["error"]["code"] == -32602


def test_a2a_requires_auth(client):
    resp = client.post(
        "/a2a",
        json={"jsonrpc": "2.0", "id": 5, "method": "agent/get", "params": {}},
    )
    assert resp.status_code == 401
