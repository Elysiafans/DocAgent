from types import SimpleNamespace

import app.services.agent_service as agent_svc
import app.services.ingestion_service as ing
from app.protocols import a2ui
from app.rag.embeddings import fake_embed_texts
from app.rag.vector_store import QdrantVectorStore
from langchain_core.messages import AIMessage

from tests.fake_model import FakeToolCallingModel

TEST_COLLECTION = "docagent_test_collection"
DOC_BYTES = "DocAgent 是多智能体知识库问答平台,支持 RAG 检索。".encode()


def test_render_message_card_unit():
    msg = SimpleNamespace(id=3, content="DocAgent 是[1]平台。", agent_type="agent:rag")
    sources = [{"doc_id": 1, "doc_name": "r.md", "score": 0.9}]
    card = a2ui.render_message_card(msg, sources)
    assert card["cardId"] == "msg-3"
    assert card["type"] == "message"
    assert card["header"]["title"]
    assert card["parts"][0]["text"] == "DocAgent 是[1]平台。"
    assert card["children"][0]["type"] == "sources"
    assert card["children"][0]["sources"][0]["doc_name"] == "r.md"


def test_render_message_card_no_sources():
    msg = SimpleNamespace(id=1, content="hi", agent_type=None)
    card = a2ui.render_message_card(msg)
    assert card["children"] == []


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
        json={"email": "a8@test.com", "password": "password123"},
    )
    tok = client.post(
        "/api/v1/auth/login",
        json={"email": "a8@test.com", "password": "password123"},
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    kb_id = client.post(
        "/api/v1/knowledge_bases", json={"name": "ui库"}, headers=h
    ).json()["id"]
    client.post(
        f"/api/v1/knowledge_bases/{kb_id}/documents",
        files={"file": ("r.md", DOC_BYTES)},
        headers=h,
    )
    return h, kb_id


def test_a2ui_render_and_fetch_card(client, monkeypatch):
    _patch(monkeypatch)
    h, kb_id = _setup(client)
    render = client.post(
        "/api/v1/a2ui/render",
        json={"kb_id": kb_id, "question": "什么是多智能体?"},
        headers=h,
    )
    assert render.status_code == 200
    body = render.json()
    card = body["card"]
    assert card["parts"][0]["text"] == "DocAgent 是[1]多智能体知识库问答平台。"
    assert card["children"][0]["sources"][0]["doc_name"] == "r.md"
    assert body["conversation_id"]
    assert body["message_id"]

    # 从已存消息渲染同一张卡片
    fetched = client.get(
        f"/api/v1/a2ui/cards/{body['message_id']}", headers=h
    )
    assert fetched.status_code == 200
    assert fetched.json()["cardId"] == card["cardId"]


def test_a2ui_card_requires_auth(client):
    resp = client.get("/api/v1/a2ui/cards/1")
    assert resp.status_code == 401


def test_a2ui_render_requires_auth(client):
    resp = client.post(
        "/api/v1/a2ui/render", json={"kb_id": 1, "question": "hi"}
    )
    assert resp.status_code == 401
