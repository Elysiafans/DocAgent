import warnings
from typing import TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

# create_react_agent 为 langgraph-prebuilt 稳定 API;
# V2 将迁移到 langchain.agents.create_agent(langchain 包未装,保留旧 API)。
from langgraph.prebuilt import create_react_agent

from app.agents.routes import ROUTES, heuristic_route, parse_route

_SUPERVISOR_PROMPT = (
    "你是任务路由。把用户意图归入四类之一,只输出一个词:\n"
    "- rag:需要检索知识库回答问题\n"
    "- summary:需要对知识库内容做总结/概括\n"
    "- compare:需要对比多个文档或方案\n"
    "- utility:计算、联网搜索或普通闲聊\n"
    "只输出一个词,不要解释。"
)

_AGENT_PROMPTS = {
    "rag": (
        "你是知识库问答员。只依据工具检索到的资料回答,"
        "资料缺失时明确说明,并用 [数字] 标注引用来源。"
    ),
    "summary": (
        "你是总结分析员。综合工具检索到的多条资料,"
        "给出结构化、分点的总结,并注明信息来源。"
    ),
    "compare": (
        "你是对比分析员。使用检索与对比工具,"
        "从多个文档/方案角度列出异同,结构清晰。"
    ),
    "utility": "你是通用工具员。用计算器/联网搜索处理问题;闲聊则直接友好回答。",
}


class AgentState(TypedDict):
    messages: list
    route: str


def build_graph(
    llm: BaseChatModel,
    tools_by_agent: dict[str, list],
    memory_context: str = "",
) -> "CompiledStateGraph":
    """构造 Supervisor + 4 agent 编排图(带 InMemorySaver 会话记忆)。

    memory_context: 用户长期记忆文本块;非空时追加到 Supervisor 与各 agent 的
    SystemPrompt,让 agent 在作答时参考已知偏好/事实。
    """
    from langgraph.graph.state import CompiledStateGraph

    def _with_memory(base: str) -> str:
        return f"{base}\n\n{memory_context}" if memory_context else base

    # create_react_agent 在 langgraph-prebuilt 1.1 打弃用告警(类别非 UserWarning),
    # 用 catch_warnings 局部抑制,构造期集中发出。
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        agents = {
            name: create_react_agent(
                llm,
                tools_by_agent.get(name, []),
                prompt=SystemMessage(content=_with_memory(_AGENT_PROMPTS[name])),
            )
            for name in ROUTES
        }

    supervisor_prompt = _with_memory(_SUPERVISOR_PROMPT)

    def supervisor(state: AgentState) -> dict:
        if state.get("route") in ROUTES:
            return {"route": state["route"]}  # 已指定路由(override/记忆)
        question = state["messages"][-1].content
        resp = llm.invoke(
            [SystemMessage(content=supervisor_prompt), HumanMessage(content=question)]
        )
        route = parse_route(getattr(resp, "content", "")) or heuristic_route(question)
        return {"route": route}

    def _make_agent_node(name):
        compiled = agents[name]

        def node(state: AgentState) -> dict:
            result = compiled.invoke({"messages": state["messages"]})
            return {"messages": result["messages"]}

        return node

    def finalize(state: AgentState) -> dict:
        last = state["messages"][-1]
        return {"messages": [AIMessage(content=getattr(last, "content", ""))]}

    def route_selector(state: AgentState) -> str:
        route = state.get("route") if state.get("route") in ROUTES else "utility"
        return f"{route}_agent"

    g = StateGraph(AgentState)
    g.add_node("supervisor", supervisor)
    for name in ROUTES:
        g.add_node(f"{name}_agent", _make_agent_node(name))
    g.add_node("finalize", finalize)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges(
        "supervisor", route_selector, {f"{n}_agent": f"{n}_agent" for n in ROUTES}
    )
    for name in ROUTES:
        g.add_edge(f"{name}_agent", "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=InMemorySaver())


def run(
    graph, question: str, thread_id: str, route_override: str | None = None
) -> "Generator[dict]":
    """流式执行:yield 结构化事件 dict(node/route/token/tool/tool_result)。"""
    initial = {
        "messages": [HumanMessage(content=question)],
        "route": route_override if route_override in ROUTES else "",
    }
    for item in graph.stream(
        initial,
        config={"configurable": {"thread_id": thread_id}},
        stream_mode=["messages", "updates"],
    ):
        if isinstance(item, tuple) and len(item) == 2:
            mode, value = item
            if mode == "messages":
                chunk, _meta = value
                ctype = getattr(chunk, "type", "")
                content = getattr(chunk, "content", "")
                if ctype == "ai" and content:
                    yield {"type": "token", "content": content}
                tcs = getattr(chunk, "tool_calls", None)
                if tcs:
                    for tc in tcs:
                        yield {
                            "type": "tool",
                            "name": tc.get("name", ""),
                            "args": tc.get("args", {}),
                        }
                elif ctype == "tool":
                    yield {
                        "type": "tool_result",
                        "name": getattr(chunk, "name", ""),
                        "content": (content or "")[:300],
                    }
            else:  # updates
                for node, update in value.items():
                    yield {"type": "node", "node": node}
                    if node == "supervisor":
                        yield {"type": "route", "route": update.get("route", "")}
                    elif node == "finalize":
                        msgs = update.get("messages") or []
                        if msgs:
                            yield {
                                "type": "answer",
                                "content": getattr(msgs[-1], "content", ""),
                            }
