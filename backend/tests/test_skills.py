import pytest
from app.agents.tools import AgentContext, build_tools
from app.protocols import skills


def _ctx():
    return AgentContext(
        db=None,
        user=None,
        kb=type("KB", (), {"id": 1})(),
        store_factory=lambda kb_id: None,
        reranker_factory=None,
    )


def test_list_skills_discovers_dir():
    names = {s["name"] for s in skills.list_skills()}
    assert {"rag_qa", "web_research"} <= names


def test_list_skills_has_descriptions():
    rag = next(s for s in skills.list_skills() if s["name"] == "rag_qa")
    assert "RAG" in rag["description"] or "知识库" in rag["description"]


def test_load_skill_returns_content():
    content = skills.load_skill("rag_qa")
    assert "knowledge_search" in content


def test_load_skill_unknown_raises():
    with pytest.raises(KeyError):
        skills.load_skill("nope")


def test_load_skill_tool_in_toolbox():
    tools = {t.name: t for t in build_tools(_ctx())}
    assert "load_skill" in tools
    out = tools["load_skill"].invoke({"skill_name": "web_research"})
    assert "web_search" in out
    missing = tools["load_skill"].invoke({"skill_name": "nope"})
    assert "未找到" in missing


def test_skills_endpoint(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "sk@test.com", "password": "password123"},
    )
    tok = client.post(
        "/api/v1/auth/login",
        json={"email": "sk@test.com", "password": "password123"},
    ).json()["access_token"]
    resp = client.get("/api/v1/skills", headers={"Authorization": f"Bearer {tok}"})
    assert resp.status_code == 200
    names = {s["name"] for s in resp.json()}
    assert "rag_qa" in names and "web_research" in names
