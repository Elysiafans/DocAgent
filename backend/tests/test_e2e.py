"""D8 全链路 E2E:注册→登录→建库→上传→就绪→SSE 对话→溯源→task_runs→长期记忆→A2UI 卡片。

单测/集成由各模块测试覆盖;本文件只验证一条贯穿完整业务链路的 HTTP 旅程。
不调用真实 SiliconFlow/DeepSeek(monkeypatch 注入 fake 模型/嵌入/重排)。
"""

import json

import app.services.agent_service as agent_svc
import app.services.ingestion_service as ing
from app.rag.embeddings import fake_embed_texts
from app.rag.vector_store import QdrantVectorStore
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from tests.fake_model import FakeToolCallingModel

TEST_COLLECTION = "docagent_test_collection"
DOC_BYTES = "DocAgent 是多智能体知识库问答平台,支持混合检索、多智能体编排与引用溯源。".encode()
EMAIL = "e2e@test.com"
PASSWORD = "password123"

FINAL_ANSWER = "DocAgent 是[1]多智能体知识库问答平台。"


class _ScriptedModel(FakeToolCallingModel):
    """按输入内容脚本化:无论多次 agent 运行(chat/render),都稳定产出。

    - 输入含 supervisor 路由提示词 → 决策 "rag"
    - 输入含 ToolMessage(工具结果) → 最终回答(引用 [1])
    - 其余(ReAct 首轮)→ 触发 knowledge_search 工具调用
    """

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.last_input = list(messages)
        if any(
            isinstance(m, SystemMessage) and "你是任务路由" in m.content
            for m in messages
        ):
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="rag"))])
        if any(isinstance(m, ToolMessage) for m in messages):
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=FINAL_ANSWER))])
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "knowledge_search",
                                "args": {"query": "多智能体"},
                                "id": "call_e2e",
                                "type": "tool_call",
                            }
                        ],
                    )
                )
            ]
        )


def _patch(monkeypatch):
    """注入 fake 向量库 + 假 LLM(与 test_agent_chat 同款手法)。"""
    from app.rag.client import get_qdrant

    client = get_qdrant()
    if client.collection_exists(TEST_COLLECTION):
        client.delete_collection(TEST_COLLECTION)
    store = QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=8)
    store.ensure_collection()
    monkeypatch.setattr(ing, "_make_vector_store", lambda kb_id: store)
    monkeypatch.setattr(agent_svc, "_make_vector_store", lambda kb_id: store)
    monkeypatch.setattr(agent_svc, "_make_reranker", lambda: None)
    monkeypatch.setattr(
        agent_svc, "_make_chat_llm", lambda: _ScriptedModel(responses=[])
    )


def _collect_sse(resp):
    events = []
    for line in resp.iter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def test_full_journey_e2e(client, monkeypatch):
    _patch(monkeypatch)

    # ---- 1. 注册 → 登录 → me ----
    reg = client.post(
        "/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD}
    )
    assert reg.status_code == 201
    tok = client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/v1/auth/me", headers=h).json()["email"] == EMAIL

    # ---- 2. 建库 + 改名 ----
    kb_id = client.post(
        "/api/v1/knowledge_bases", json={"name": "E2E 库"}, headers=h
    ).json()["id"]
    patched = client.patch(
        f"/api/v1/knowledge_bases/{kb_id}", json={"description": "全链路测试"}, headers=h
    ).json()
    assert patched["description"] == "全链路测试"

    # ---- 3. 上传 → 就绪(TestClient 后台摄取同步执行)----
    r = client.post(
        f"/api/v1/knowledge_bases/{kb_id}/documents",
        files={"file": ("e2e.md", DOC_BYTES)},
        headers=h,
    )
    assert r.status_code == 201
    doc_id = r.json()["id"]
    doc = client.get(f"/api/v1/documents/{doc_id}", headers=h).json()
    assert doc["status"] == "ready"
    assert doc["chunk_count"] >= 1

    # ---- 4. SSE 多智能体对话 ----
    with client.stream(
        "POST",
        "/api/v1/chat/agent",
        json={"kb_id": kb_id, "question": "这是什么平台?"},
        headers=h,
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/event-stream")
        events = _collect_sse(resp)

    types = [e["type"] for e in events]
    for t in ("route", "node", "token", "tool", "answer", "sources", "done"):
        assert t in types, f"SSE 缺事件 {t}"
    ans = next(e for e in events if e["type"] == "answer")["content"]
    assert "DocAgent" in ans and "[1]" in ans  # 回答引用 [1]
    sources = next(e for e in events if e["type"] == "sources")["sources"]
    assert sources and sources[0]["doc_name"] == "e2e.md"
    conv_id = events[-1]["conversation_id"]

    # 会话消息持久化(含溯源)
    msgs = client.get(f"/api/v1/conversations/{conv_id}/messages", headers=h).json()
    assert len(msgs) == 2 and msgs[1]["role"] == "assistant"

    # ---- 5. task_runs 可观测 ----
    runs = client.get("/api/v1/task_runs", headers=h).json()
    run = next(r for r in runs if r["type"] == "agent")
    assert run["status"] == "success"
    detail = client.get(f"/api/v1/task_runs/{run['id']}", headers=h).json()
    assert detail["trace"] and detail["trace"]["events"]

    # ---- 6. 长期记忆写入 + 命中 ----
    client.post(
        "/api/v1/memories", json={"content": "用户偏好简洁回答", "kind": "note"}, headers=h
    )
    hits = client.get(
        "/api/v1/memories/search", params={"q": "偏好"}, headers=h
    ).json()
    assert any(m["content"] == "用户偏好简洁回答" for m in hits)

    # ---- 7. A2UI 卡片渲染 + 回取 ----
    body = client.post(
        "/api/v1/a2ui/render",
        json={"kb_id": kb_id, "question": "一句话介绍平台", "route": "rag"},
        headers=h,
    ).json()
    card = body["card"]
    assert card["cardId"]
    assert card["parts"][0]["text"] == "DocAgent 是[1]多智能体知识库问答平台。"
    fetched = client.get(f"/api/v1/a2ui/cards/{body['message_id']}", headers=h)
    assert fetched.status_code == 200
    assert fetched.json()["cardId"] == card["cardId"]
