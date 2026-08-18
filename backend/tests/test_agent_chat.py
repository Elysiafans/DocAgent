import json

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


def _setup(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "a5@test.com", "password": "password123"},
    )
    tok = client.post(
        "/api/v1/auth/login",
        json={"email": "a5@test.com", "password": "password123"},
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    kb_id = client.post(
        "/api/v1/knowledge_bases", json={"name": "agent库"}, headers=h
    ).json()["id"]
    client.post(
        f"/api/v1/knowledge_bases/{kb_id}/documents",
        files={"file": ("r.md", DOC_BYTES)},
        headers=h,
    )
    return h, kb_id


def _collect_sse(resp):
    events = []
    for line in resp.iter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def test_agent_chat_sse_flow(client, monkeypatch):
    _patch(monkeypatch)
    h, kb_id = _setup(client)
    with client.stream(
        "POST",
        "/api/v1/chat/agent",
        json={"kb_id": kb_id, "question": "什么是多智能体?"},
        headers=h,
    ) as resp:
        assert resp.status_code == 200, resp.text
        assert resp.headers.get("content-type", "").startswith("text/event-stream")
        events = _collect_sse(resp)

    types = [e["type"] for e in events]
    assert types.index("route") >= 0 and events[types.index("route")]["route"] == "rag"
    assert "node" in types
    assert "token" in types
    assert "tool" in types  # knowledge_search 被调用
    ans = next(e for e in events if e["type"] == "answer")["content"]
    assert "DocAgent" in ans
    assert "done" in types

    # 持久化:会话 + 消息 + sources
    conv_id = events[-1]["conversation_id"]
    convs = client.get("/api/v1/conversations", headers=h).json()
    assert any(c["id"] == conv_id for c in convs)
    msgs = client.get(f"/api/v1/conversations/{conv_id}/messages", headers=h).json()
    assert len(msgs) == 2
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["sources"] and msgs[1]["sources"][0]["doc_name"] == "r.md"

    # task_runs 可观测
    runs = client.get("/api/v1/task_runs", headers=h).json()
    assert any(r["type"] == "agent" and r["status"] == "success" for r in runs)


def test_agent_chat_route_override(client, monkeypatch):
    _patch(monkeypatch)
    h, kb_id = _setup(client)
    with client.stream(
        "POST",
        "/api/v1/chat/agent",
        json={"kb_id": kb_id, "question": "随便聊聊", "route": "utility"},
        headers=h,
    ) as resp:
        events = _collect_sse(resp)
    types = [e["type"] for e in events]
    assert "done" in types


def test_agent_chat_requires_auth(client):
    with client.stream(
        "POST", "/api/v1/chat/agent", json={"kb_id": 1, "question": "hi"}
    ) as resp:
        assert resp.status_code == 401


def test_agent_chat_unknown_kb_returns_404(client, monkeypatch):
    _patch(monkeypatch)
    client.post(
        "/api/v1/auth/register",
        json={"email": "a6@test.com", "password": "password123"},
    )
    tok = client.post(
        "/api/v1/auth/login",
        json={"email": "a6@test.com", "password": "password123"},
    ).json()["access_token"]
    with client.stream(
        "POST",
        "/api/v1/chat/agent",
        json={"kb_id": 999, "question": "hi"},
        headers={"Authorization": f"Bearer {tok}"},
    ) as resp:
        assert resp.status_code == 404
