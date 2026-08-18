import json

import app.services.agent_service as agent_svc
from app.agents.tools import AgentContext
from app.protocols.mcp_server import McpServer
from app.protocols.mcp_tools import mcp_tool_specs
from app.rag.chunking import ChunkRecord
from app.rag.embeddings import fake_embed_texts
from app.rag.vector_store import QdrantVectorStore

TEST_COLLECTION = "docagent_test_collection"


def _fake_store():
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
            for i, t in enumerate(
                ["DocAgent 支持 PDF 解析", "DocAgent 支持 Word 解析"]
            )
        ],
    )
    return store


def _server():
    store = _fake_store()

    def ctx_factory(kb_id):
        return AgentContext(
            db=None,
            user=None,
            kb=type("KB", (), {"id": kb_id})(),
            store_factory=lambda kb_id: store,
            reranker_factory=None,
        )

    return McpServer(mcp_tool_specs(), ctx_factory)


def _req(method, params, rid=1):
    return {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}


def test_mcp_initialize_handshake():
    resp = _server().handle(_req("initialize", {"protocolVersion": "2025-03-26"}))
    result = resp["result"]
    assert result["protocolVersion"] == "2025-03-26"
    assert result["capabilities"]["tools"]["listChanged"] is False
    assert result["serverInfo"]["name"] == "docagent-mcp"
    assert result["serverInfo"]["version"]


def test_mcp_tools_list():
    resp = _server().handle(_req("tools/list", {}))
    names = {t["name"] for t in resp["result"]["tools"]}
    assert names == {
        "knowledge_search",
        "compare_documents",
        "calculator",
        "web_search",
    }
    ks = next(t for t in resp["result"]["tools"] if t["name"] == "knowledge_search")
    assert ks["description"]
    assert "kb_id" in ks["inputSchema"]["required"]
    assert "query" in ks["inputSchema"]["required"]


def test_mcp_tools_call_knowledge_search():
    resp = _server().handle(
        _req(
            "tools/call",
            {
                "name": "knowledge_search",
                "arguments": {"kb_id": 1, "query": "DocAgent 支持"},
            },
        )
    )
    text = resp["result"]["content"][0]["text"]
    assert "DocAgent" in text and "[1]" in text


def test_mcp_unknown_method_error():
    resp = _server().handle(_req("nope", {}))
    assert resp["error"]["code"] == -32601


def test_mcp_parse_error():
    server = _server()
    # 缺 method / 非法请求 -> -32600
    resp = server.handle({"jsonrpc": "2.0", "id": 1, "params": {}})
    assert resp["error"]["code"] == -32600


def _auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "mcp@test.com", "password": "password123"},
    )
    tok = client.post(
        "/api/v1/auth/login",
        json={"email": "mcp@test.com", "password": "password123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_mcp_http_json_mode(client, monkeypatch):
    store = _fake_store()
    monkeypatch.setattr(agent_svc, "_make_vector_store", lambda kb_id: store)
    h = _auth_headers(client)
    kb_id = client.post(
        "/api/v1/knowledge_bases", json={"name": "mcp库"}, headers=h
    ).json()["id"]
    resp = client.post(
        "/mcp",
        json=_req("tools/call", {"name": "knowledge_search", "arguments": {"kb_id": kb_id, "query": "支持"}}),
        headers={**h, "Accept": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["content"][0]["text"]


def test_mcp_http_sse_mode(client, monkeypatch):
    store = _fake_store()
    monkeypatch.setattr(agent_svc, "_make_vector_store", lambda kb_id: store)
    h = _auth_headers(client)
    kb_id = client.post(
        "/api/v1/knowledge_bases", json={"name": "mcp库2"}, headers=h
    ).json()["id"]
    with client.stream(
        "POST",
        "/mcp",
        json=_req("tools/list", {}),
        headers={**h, "Accept": "text/event-stream"},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/event-stream")
        data = [line for line in resp.iter_lines() if line.startswith("data: ")]
    assert any("tools" in json.loads(d[6:]).get("result", {}) for d in data)


def test_mcp_requires_auth(client):
    resp = client.post("/mcp", json=_req("tools/list", {}))
    assert resp.status_code == 401
