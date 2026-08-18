from app.agents import routes
from app.agents.graph import build_graph
from app.rag.embeddings import fake_embed_texts
from app.rag.vector_store import QdrantVectorStore
from langchain_core.messages import AIMessage, HumanMessage

from tests.fake_model import FakeToolCallingModel

TEST_COLLECTION = "docagent_test_collection"


def _tools(kb_id=1):
    from app.agents.tools import AgentContext, build_tools
    from app.rag.client import get_qdrant

    client = get_qdrant()
    if client.collection_exists(TEST_COLLECTION):
        client.delete_collection(TEST_COLLECTION)
    store = QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=8)
    store.ensure_collection()
    ctx = AgentContext(
        db=None,
        user=None,
        kb=type("KB", (), {"id": kb_id})(),
        store_factory=lambda kb_id: store,
        reranker_factory=None,
    )
    return build_tools(ctx)


def _collect_ai_text(events) -> str:
    parts = []
    for e in events:
        if isinstance(e, tuple) and len(e) == 2 and e[0] == "messages":
            chunk = e[1][0]
            if getattr(chunk, "type", "") == "ai" and chunk.content:
                parts.append(chunk.content)
    return "".join(parts)


def _scripted(route_text, final_answer):
    """supervisor 返回 route;agent 第一次调用工具,第二次给答案。"""
    return [
        AIMessage(content=route_text),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "knowledge_search",
                    "args": {"query": "DocAgent"},
                    "id": "call_1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content=final_answer),
    ]


def test_graph_rag_route_runs_end_to_end():
    llm = FakeToolCallingModel(_scripted("rag", "答案是 DocAgent。"))
    graph = build_graph(
        llm,
        {"rag": _tools(), "summary": [], "compare": [], "utility": []},
    )
    events = list(
        graph.stream(
            {"messages": [HumanMessage(content="DocAgent 是什么?")]},
            config={"configurable": {"thread_id": "t1"}},
            stream_mode=["messages", "updates"],
        )
    )
    text = _collect_ai_text(events)
    assert "DocAgent" in text  # 最终答案在事件流中出现


def test_graph_route_override_skips_supervisor_classify():
    # route 已在初始状态给定,supervisor 不再分类:脚本只给 agent 两轮(工具+回答)
    llm = FakeToolCallingModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "knowledge_search",
                        "args": {"query": "DocAgent"},
                        "id": "call_1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="工具回答完成"),
        ]
    )
    graph = build_graph(
        llm,
        {"rag": _tools(), "summary": [], "compare": [], "utility": []},
    )
    events = list(
        graph.stream(
            {"messages": [HumanMessage(content="随便聊聊")], "route": "rag"},
            config={"configurable": {"thread_id": "t2"}},
            stream_mode=["messages", "updates"],
        )
    )
    text = _collect_ai_text(events)
    assert "工具回答完成" in text


def test_heuristic_routes():
    assert routes.heuristic_route("帮我总结一下这篇文章") == "summary"
    assert routes.heuristic_route("对比一下方案A和方案B") == "compare"
    assert routes.heuristic_route("计算 12*34 等于多少") == "utility"
    assert routes.heuristic_route("DocAgent 支持什么格式") == "rag"


def test_parse_route():
    assert routes.parse_route("rag") == "rag"
    assert routes.parse_route("rag。") == "rag"
    assert routes.parse_route("summary") == "summary"
    assert routes.parse_route("随便聊聊") is None
