import app.services.agent_service as agent_svc
import app.services.ingestion_service as ing
from langchain_core.messages import AIMessage

from app.rag.embeddings import fake_embed_texts
from app.rag.vector_store import QdrantVectorStore
from tests.fake_model import FakeToolCallingModel

TEST_COLLECTION = "docagent_test_collection"
DOC_BYTES = "DocAgent 是多智能体知识库问答平台,支持 RAG 检索。".encode()


def _register(client, email):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    tok = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_memory_api_crud(client):
    h = _register(client, "mem1@test.com")
    resp = client.post(
        "/api/v1/memories",
        json={"content": "用户偏好中文回答", "kind": "preference"},
        headers=h,
    )
    assert resp.status_code == 201
    mem_id = resp.json()["id"]
    lst = client.get("/api/v1/memories", headers=h).json()
    assert any(m["content"] == "用户偏好中文回答" for m in lst)
    found = client.get("/api/v1/memories/search", params={"q": "偏好"}, headers=h).json()
    assert len(found) == 1
    assert client.delete(f"/api/v1/memories/{mem_id}", headers=h).status_code == 204
    assert client.get("/api/v1/memories", headers=h).json() == []


def test_memory_delete_other_user_404(client):
    h_a = _register(client, "mem2a@test.com")
    mem_id = client.post(
        "/api/v1/memories", json={"content": "A 的记忆"}, headers=h_a
    ).json()["id"]
    h_b = _register(client, "mem2b@test.com")  # 不同用户 B
    resp = client.delete(f"/api/v1/memories/{mem_id}", headers=h_b)
    assert resp.status_code == 404


def test_memory_service_crud_and_context():
    from sqlalchemy.orm import Session

    from app.db.session import SessionLocal
    from app.models import User
    from app.services import memory_service

    db: Session = SessionLocal()
    try:
        u = User(email="memsvc@test.com", hashed_password="x")
        db.add(u)
        db.commit()
        db.refresh(u)
        m = memory_service.add_memory(db, u, "用户偏好中文回答", kind="preference")
        assert memory_service.list_memories(db, u)[0].content == "用户偏好中文回答"
        assert len(memory_service.search_memories(db, u, "偏好")) == 1
        ctx = memory_service.build_memory_context(db, u)
        assert "用户偏好中文回答" in ctx and "preference" in ctx
        memory_service.delete_memory(db, u, m.id)
        assert memory_service.list_memories(db, u) == []
    finally:
        db.close()


def test_graph_memory_context_injected_in_system_prompt():
    from app.agents.graph import build_graph
    from app.agents.tools import AgentContext, build_tools
    from langchain_core.messages import HumanMessage

    ctx = AgentContext(
        db=None,
        user=None,
        kb=type("KB", (), {"id": 1})(),
        store_factory=lambda kb_id: None,
        reranker_factory=None,
    )
    llm = FakeToolCallingModel(
        [
            AIMessage(content="rag"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "knowledge_search",
                        "args": {"query": "x"},
                        "id": "c1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="完成"),
        ]
    )
    graph = build_graph(
        llm,
        {"rag": build_tools(ctx), "summary": [], "compare": [], "utility": []},
        memory_context="用户长期记忆:用户偏好中文回答",
    )
    list(
        graph.stream(
            {"messages": [HumanMessage(content="你好")], "route": "rag"},
            config={"configurable": {"thread_id": "t"}},
            stream_mode=["messages", "updates"],
        )
    )
    # supervisor 或 agent 的系统提示应含记忆块
    first_input = llm.last_input
    joined = "\n".join(
        str(getattr(m, "content", "")) for m in (first_input or [])
    )
    assert "用户长期记忆" in joined or "用户偏好中文回答" in joined


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


def test_memory_injected_into_agent_ask(client, monkeypatch):
    llm = _patch(monkeypatch)
    h = _register(client, "memi@test.com")
    kb_id = client.post(
        "/api/v1/knowledge_bases", json={"name": "mem库"}, headers=h
    ).json()["id"]
    client.post(
        f"/api/v1/knowledge_bases/{kb_id}/documents",
        files={"file": ("r.md", DOC_BYTES)},
        headers=h,
    )
    client.post(
        "/api/v1/memories",
        json={"content": "用户偏好中文回答", "kind": "preference"},
        headers=h,
    )
    resp = client.post(
        "/a2a",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {
                "message": {"parts": [{"kind": "text", "text": "什么是多智能体?"}]},
                "metadata": {"kb_id": kb_id},
            },
        },
        headers=h,
    )
    assert resp.json()["result"]["status"] == "completed"
    # ask 全链路:supervisor/agent 的系统提示应含记忆
    joined = "\n".join(
        str(getattr(m, "content", "")) for m in (llm.last_input or [])
    )
    assert "用户偏好中文回答" in joined
