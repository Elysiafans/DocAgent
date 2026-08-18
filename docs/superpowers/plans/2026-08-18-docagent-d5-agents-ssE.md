# DocAgent D5 —— 多智能体编排(LangGraph)+ SSE 流式实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 上线多智能体编排:`Supervisor` 路由 + 4 个专职 agent(基于 `create_react_agent`,ReAct + 工具)+ 共享工具集 + 会话记忆(短时,InMemorySaver checkpointer)+ SSE 流式 `/chat/agent`,并把每次运行的节点调用链/工具调用写入 `task_runs.trace`(可观测)。

**Architecture:**
```
用户提问(SSE POST /chat/agent)
   │
┌──▼───────────────┐
│ supervisor(LLM 分类 │  route ∈ {rag, summary, compare, utility}
│  +关键词兜底)        │
└──┬────┬────┬────┬──┘
   ▼    ▼    ▼    ▼
 rag  summary compare utility   ← 各为 create_react_agent 子图节点
 agent agent   agent  agent       (ReAct + 工具)
   │    │    │    │
   └────┴────┴────┴──► finalize(抽最终答案)
   ▼
 answer + sources(SSE 事件流) + 持久化 Message + task_runs.trace
```

**Tech Stack:** langgraph==1.2.10 / langgraph-checkpoint==4.1.1 / langgraph-prebuilt==1.1.0 / langgraph-sdk==0.4.2 / langsmith==0.10.11(均已在 yy 环境,补锁进 requirements)+ duckduckgo-search==8.1.1(需 pip 安装)。SSE 用 Starlette 内置 `StreamingResponse`,不引 sse_starlette。

**已探测确认:**
- `create_react_agent`(langgraph-prebuilt 1.1.0)可用,但打 `LangGraphDeprecatedSinceV10` 警告(新 API 在未安装的 `langchain.agents`,故保留旧 API,注释说明)。
- `GenericFakeChatModel` 不支持 `bind_tools` → 测试需自定义 `FakeToolCallingModel`(继承 `BaseChatModel`,实现 `bind_tools` + 脚本化 `_generate`)。
- 多模式 stream `stream_mode=["messages","updates"]` 产出 `(mode, value)` 元组;嵌套 react agent 的 messages 会传播;`chunk.type` ∈ {human, ai, tool};tool_calls 在 AI message 上;metadata 带 `langgraph_node`。
- 子图作节点需包一层 `def node(state): return compiled.invoke({...})`。
- `@tool` 必须带 docstring(langchain-core 1.5.2 要求)。
- task_runs 模型目前无 user_id/conv_id → 需 Alembic 迁移补两列。

**Global Constraints:** 同 D1-D4(WSL + `yy`、测试不触网、真实冒烟用 `.env` key、密钥不提交、conventional commits)。测试里 agent 的 LLM 用 `FakeToolCallingModel`,工具用 fake store/reranker;SSE 用 `client.stream("POST", ...)` 解析 `data:` 行。

---

### Task 1: 依赖 + LLM 绑定 + 共享工具集

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/agents/__init__.py`
- Create: `backend/app/agents/llm.py`
- Create: `backend/app/agents/tools.py`
- Test: `backend/tests/test_tools.py`

**Interfaces:**
- `agents.llm.get_chat_llm() -> BaseChatModel`:`ChatOpenAI(model=DEEPSEEK_CHAT_MODEL, base_url=DEEPSEEK_BASE_URL, api_key=DEEPSEEK_API_KEY, temperature=0.2)`
- `agents.tools.AgentContext(db, user, kb, store_factory, reranker_factory, collected_sources: list)`
- `agents.tools.build_tools(ctx) -> list[BaseTool]`:返回 `[knowledge_search, calculator, web_search, compare_documents]`
- `knowledge_search(query, top_k=5)`:D4 `retrieve()` + doc_names + `assemble_context()`;命中片段追加到 `ctx.collected_sources`
- `calculator(expr)`:AST 安全求值(禁 eval)
- `web_search(query)`:DuckDuckGo(经模块级 `_web_search_impl` 缝,测试打桩)
- `compare_documents(query, doc_names: list[str])`:按文档分组对比

- [ ] **Step 1: 写工具测试(先失败)**

创建 `backend/tests/test_tools.py`:

```python
import app.agents.tools as tools_mod
from app.agents.tools import AgentContext, build_tools
from app.rag.embeddings import fake_embed_texts
from app.rag.vector_store import QdrantVectorStore

TEST_COLLECTION = "docagent_test_collection"


def _ctx():
    from app.rag.client import get_qdrant

    client = get_qdrant()
    if client.collection_exists(TEST_COLLECTION):
        client.delete_collection(TEST_COLLECTION)
    store = QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=8)
    store.ensure_collection()
    from app.rag.chunking import ChunkRecord

    store.upsert_document(
        7, 1,
        [
            ChunkRecord(index=i, content=t, char_count=len(t), hash=f"h{i}",
                        meta={"kb_id": 1, "doc_id": 7, "chunk_index": i})
            for i, t in enumerate(["DocAgent 支持 PDF 解析", "DocAgent 支持 Word 解析"])
        ],
    )
    ctx = AgentContext(
        db=None, user=None, kb=type("KB", (), {"id": 1})(),
        store_factory=lambda kb_id: store,
        reranker_factory=None,
    )
    return ctx


def test_knowledge_search_formats_and_collects_sources():
    ctx = _ctx()
    tools = {t.name: t for t in build_tools(ctx)}
    out = tools["knowledge_search"].invoke({"query": "DocAgent 支持", "top_k": 5})
    assert "[1]" in out and "DocAgent" in out
    assert ctx.collected_sources and ctx.collected_sources[0]["doc_id"] == 7


def test_calculator_safe_arith():
    ctx = _ctx()
    tools = {t.name: t for t in build_tools(ctx)}
    assert tools["calculator"].invoke({"expr": "(1 + 2) * 3"}) == "9"
    assert tools["calculator"].invoke({"expr": "10 / 4"}) == "2.5"


def test_calculator_rejects_unsafe():
    ctx = _ctx()
    tools = {t.name: t for t in build_tools(ctx)}
    out = tools["calculator"].invoke({"expr": "__import__('os').system('x')"})
    assert "不支持" in out  # 安全拒绝


def test_web_search_uses_impl(monkeypatch):
    def fake_impl(q):
        return "DDG: result1 / result2"
    monkeypatch.setattr(tools_mod, "_web_search_impl", fake_impl)
    ctx = _ctx()
    tools = {t.name: t for t in build_tools(ctx)}
    assert "result1" in tools["web_search"].invoke({"query": "python"})


def test_compare_documents_groups_by_doc():
    ctx = _ctx()
    tools = {t.name: t for t in build_tools(ctx)}
    out = tools["compare_documents"].invoke(
        {"query": "DocAgent", "doc_names": ["docagent.md"]}
    )
    assert "docagent.md" in out
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_tools.py -v
```

期望:FAIL(ModuleNotFoundError)。

- [ ] **Step 3: 锁依赖 + 安装**

编辑 `backend/requirements.txt`,在 langchain 组追加:

```text
langgraph==1.2.10
langgraph-checkpoint==4.1.1
langgraph-prebuilt==1.1.0
langgraph-sdk==0.4.2
langsmith==0.10.11
duckduckgo-search==8.1.1
```

安装(仅新增的两个包):

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pip install duckduckgo-search==8.1.1
```

> 若 duckduckgo-search 安装失败或运行时网络不可用:`_web_search_impl` 返回明确离线提示,工具仍演示 tool-calling。

- [ ] **Step 4: 实现 llm.py**

创建 `backend/app/agents/llm.py`:

```python
from langchain_openai import ChatOpenAI

from app.core.config import get_settings


def get_chat_llm() -> ChatOpenAI:
    """DeepSeek(deepseek-v4-flash)OpenAI 兼容绑定,供 create_react_agent / supervisor 使用。"""
    s = get_settings()
    return ChatOpenAI(
        model=s.DEEPSEEK_CHAT_MODEL,
        base_url=s.DEEPSEEK_BASE_URL,
        api_key=s.DEEPSEEK_API_KEY,
        temperature=0.2,
        timeout=60,
    )
```

- [ ] **Step 5: 实现 tools.py**

创建 `backend/app/agents/tools.py`:

```python
import ast
import operator
from dataclasses import dataclass, field
from typing import Any, Callable

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, KnowledgeBase, User
from app.rag.reranker import Reranker
from app.rag.retrieval import assemble_context, retrieve
from app.rag.vector_store import QdrantVectorStore


@dataclass
class AgentContext:
    """每次 agent 运行共享的上下文:持有 DB/归属校验 + 注入式 Provider 工厂。"""

    db: Session | None
    user: User | None
    kb: KnowledgeBase
    store_factory: Callable[[int], QdrantVectorStore]
    reranker_factory: Callable[[], Reranker | None] | None = None
    collected_sources: list[dict[str, Any]] = field(default_factory=list)


# ---- 安全计算 ----
_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("unsupported expression")


def _web_search_impl(query: str) -> str:
    """DuckDuckGo 搜索(测试/离线打桩缝)。"""
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return "没有搜索到结果"
        return "\n".join(
            f"- {r.get('title', '')}: {r.get('body', '')[:120]}"
            for r in results
        )
    except Exception as e:  # noqa: BLE001
        return f"联网搜索暂不可用(离线/超时):{type(e).__name__}"


def build_tools(ctx: AgentContext) -> list:
    """按 AgentContext 构造共享工具集(闭包绑定库归属与 Provider)。"""

    @tool
    def knowledge_search(query: str, top_k: int = 5) -> str:
        """在用户知识库中做混合检索,返回带 [编号] 的片段与来源,供回答引用。"""
        store = ctx.store_factory(ctx.kb.id)
        reranker = ctx.reranker_factory() if ctx.reranker_factory else None
        chunks = retrieve(
            store, reranker, query, ctx.kb.id, top_k=top_k, top_n=min(top_k, 8)
        )
        doc_names: dict[int, str] = {}
        if chunks and ctx.db is not None:
            doc_ids = {c.doc_id for c in chunks}
            doc_names = {
                d.id: d.name
                for d in ctx.db.execute(
                    select(Document).where(Document.id.in_(doc_ids))
                ).scalars()
            }
        ctx.collected_sources.extend(
            {
                "doc_id": c.doc_id,
                "doc_name": doc_names.get(c.doc_id),
                "chunk_index": c.chunk_index,
                "content": c.content,
                "score": round(c.score, 4),
            }
            for c in chunks
        )
        return assemble_context(chunks, doc_names) or "知识库中没有相关内容"

    @tool
    def calculator(expr: str) -> str:
        """安全计算算术表达式(支持 + - * / % ** 与括号),输入形如 \"(1+2)*3\"。"""
        try:
            val = _safe_eval(ast.parse(expr, mode="eval"))
            return str(val)
        except (ValueError, SyntaxError, ZeroDivisionError):
            return "表达式不支持或非法"

    @tool
    def web_search(query: str) -> str:
        """联网搜索最新信息(DuckDuckGo),返回前几条标题与摘要。"""
        return _web_search_impl(query)

    @tool
    def compare_documents(query: str, doc_names: list[str]) -> str:
        """对比分析:按文档分组汇总检索结果,输出每份文档的相关内容。"""
        store = ctx.store_factory(ctx.kb.id)
        reranker = ctx.reranker_factory() if ctx.reranker_factory else None
        chunks = retrieve(
            store, reranker, query, ctx.kb.id, top_k=20, top_n=12
        )
        names = set(doc_names)
        groups: dict[str, list[str]] = {}
        for c in chunks:
            if c.doc_name and c.doc_name in names:
                groups.setdefault(c.doc_name, []).append(c.content)
        if not groups:
            return "未检索到指定文档的相关内容"
        return "\n".join(
            f"[{name}]\n" + "\n".join(f"  - {t[:100]}" for t in texts)
            for name, texts in groups.items()
        )

    return [knowledge_search, calculator, web_search, compare_documents]
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_tools.py -v
```

期望:5 passed。

- [ ] **Step 7: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/requirements.txt backend/app/agents/ backend/tests/test_tools.py
git commit -m "feat: add agent llm binding and shared tools (rag/calc/web/compare)"
```

---

### Task 2: 智能体图(Supervisor + 4 agents, LangGraph)

**Files:**
- Create: `backend/tests/fake_model.py`
- Create: `backend/app/agents/routes.py`
- Create: `backend/app/agents/graph.py`
- Test: `backend/tests/test_agents_graph.py`

**Interfaces:**
- `tests/fake_model.FakeToolCallingModel(responses)`:脚本化工具调用模型(bind_tools 无操作,_generate 依次弹出脚本)
- `agents.routes.ROUTES = {"rag","summary","compare","utility"}`;`parse_route(text) -> str | None`;`heuristic_route(question) -> str`
- `agents.graph.build_graph(llm, tools_by_agent: dict[str, list]) -> CompiledStateGraph`(InMemorySaver checkpointer)
- `agents.graph.run(graph, question, thread_id, route_override=None) -> Generator[dict]`:产出流式事件 dict

- [ ] **Step 1: 写 fake 模型与图测试(先失败)**

创建 `backend/tests/fake_model.py`:

```python
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult


class FakeToolCallingModel(BaseChatModel):
    """按脚本依次返回消息的模型:可含 tool_calls 触发 ReAct 工具调用。"""

    responses: list
    tools: list | None = None

    def __init__(self, responses, **kwargs):
        super().__init__(responses=list(responses), **kwargs)

    @property
    def _llm_type(self) -> str:
        return "fake-tool-calling"

    def bind_tools(self, tools, **kwargs):
        self.tools = list(tools)
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if not self.responses:
            from langchain_core.messages import AIMessage
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="完成"))])
        return ChatResult(generations=[ChatGeneration(message=self.responses.pop(0))])
```

创建 `backend/tests/test_agents_graph.py`:

```python
from langchain_core.messages import AIMessage, HumanMessage

import app.agents.routes as routes
from app.agents.graph import build_graph
from app.rag.embeddings import fake_embed_texts
from app.rag.vector_store import QdrantVectorStore
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
        db=None, user=None, kb=type("KB", (), {"id": kb_id})(),
        store_factory=lambda kb_id: store, reranker_factory=None,
    )
    return build_tools(ctx)


def _scripted(route_text, final_answer):
    """supervisor 返回 route;agent 第一次调用工具,第二次给答案。"""
    return [
        AIMessage(content=route_text),
        AIMessage(content="", tool_calls=[{
            "name": "knowledge_search", "args": {"query": "DocAgent"},
            "id": "call_1", "type": "tool_call",
        }]),
        AIMessage(content=final_answer),
    ]


def test_graph_rag_route_runs_end_to_end():
    llm = FakeToolCallingModel(_scripted("rag", "答案是 DocAgent。"))
    graph = build_graph(llm, {"rag": _tools(), "utility": [], "summary": [], "compare": []})
    events = list(graph.stream(
        {"messages": [HumanMessage(content="DocAgent 是什么?")]},
        config={"configurable": {"thread_id": "t1"}},
        stream_mode=["messages", "updates"],
    ))
    # 收集最终 AI 文本
    texts = [
        (c.content if hasattr(c, "content") else "") for m, c in [(e[0], e[1]) for e in events if isinstance(e, tuple) and e[0] == "messages"] for c in [c_]
    ]
    # 简化断言:最终答案在 events 里出现
    joined = "".join(
        e[1][0].content for e in events if isinstance(e, tuple) and e[0] == "messages" and getattr(e[1][0], "type", "") == "ai"
    )
    assert "DocAgent" in joined


def test_heuristic_routes():
    assert routes.heuristic_route("帮我总结一下这篇文章") == "summary"
    assert routes.heuristic_route("对比一下方案A和方案B") == "compare"
    assert routes.heuristic_route("计算 12*34 等于多少") == "utility"
    assert routes.heuristic_route("DocAgent 支持什么格式") == "rag"


def test_parse_route_unknown():
    assert routes.parse_route("随便聊聊") is None
    assert routes.parse_route("rag") == "rag"
    assert routes.parse_route("总结") == "summary"
```

> 说明:图测试的断言以"事件流里出现最终 AI 文本"为准(事件形状已探测确认:tuple(mode, value))。更细的 node/token 断言放到 Task 3 的 SSE 测试。

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_agents_graph.py -v
```

期望:FAIL。

- [ ] **Step 3: 实现 routes.py**

创建 `backend/app/agents/routes.py`:

```python
import re

ROUTES = ("rag", "summary", "compare", "utility")

_SUMMARY_KEYS = ("总结", "概括", "摘要", "要点", "概述")
_COMPARE_KEYS = ("对比", "比较", "区别", "异同", "哪个好")
_UTILITY_KEYS = ("计算", "等于", "算式", "公式", "搜索", "网上", "天气", "最新")


def parse_route(text: str) -> str | None:
    """从 LLM 返回里提取路由关键词。"""
    t = (text or "").strip().lower()
    for r in ROUTES:
        if re.fullmatch(r"[\"']?%s[\"']?[\s。.!！]*" % re.escape(r), t):
            return r
    if "rag" in t:
        return "rag"
    if "summary" in t:
        return "summary"
    if "compare" in t:
        return "compare"
    if "utility" in t:
        return "utility"
    return None


def heuristic_route(question: str) -> str:
    """关键词兜底分类:无 LLM 或 LLM 输出异常时使用。"""
    q = question or ""
    if any(k in q for k in _COMPARE_KEYS):
        return "compare"
    if any(k in q for k in _SUMMARY_KEYS):
        return "summary"
    if any(k in q for k in _UTILITY_KEYS):
        return "utility"
    return "rag"
```

- [ ] **Step 4: 实现 graph.py**

创建 `backend/app/agents/graph.py`:

```python
import warnings
from typing import TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent  # 稳定 API;V2 将迁移到 langchain.agents

from app.agents.routes import ROUTES, heuristic_route, parse_route

warnings.filterwarnings(
    "ignore", message=".*create_react_agent.*", category=UserWarning
)

_SUPERVISOR_PROMPT = (
    "你是任务路由。把用户意图归入四类之一,只输出一个词:\n"
    "- rag:需要检索知识库回答问题\n"
    "- summary:需要对知识库内容做总结/概括\n"
    "- compare:需要对比多个文档或方案\n"
    "- utility:计算、联网搜索或普通闲聊\n"
    "只输出一个词,不要解释。"
)

_AGENT_PROMPTS = {
    "rag": "你是知识库问答员。只依据工具检索到的资料回答,缺失时说明,并用 [数字] 标注引用来源。",
    "summary": "你是总结分析员。综合工具检索到的多条资料,给出结构化、分点的总结。",
    "compare": "你是对比分析员。使用检索与对比工具,从多个文档/方案角度列出异同,结构清晰。",
    "utility": "你是通用工具员。用计算器/联网搜索处理问题;闲聊则直接友好回答。",
}


class AgentState(TypedDict):
    messages: list
    route: str


def build_graph(
    llm: BaseChatModel, tools_by_agent: dict[str, list]
) -> "CompiledStateGraph":
    """构造 Supervisor + 4 agent 编排图(带 InMemorySaver 会话记忆)。"""
    from langgraph.graph.state import CompiledStateGraph

    agents = {
        name: create_react_agent(
            llm,
            tools_by_agent.get(name, []),
            state_modifier=SystemMessage(content=_AGENT_PROMPTS[name]),
        )
        for name in ROUTES
    }

    def supervisor(state: AgentState) -> dict:
        if state.get("route") in ROUTES:
            return {"route": state["route"]}  # 已指定路由(override/记忆)
        question = state["messages"][-1].content
        resp = llm.invoke(
            [SystemMessage(content=_SUPERVISOR_PROMPT), HumanMessage(content=question)]
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
        return state.get("route") if state.get("route") in ROUTES else "utility"

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
```

> 说明:`state_modifier` 让每个 react agent 拥有不同的 system prompt(create_react_agent 支持)。supervisor 用 `llm.invoke`(非流式)分类一次,成本低且确定。

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_agents_graph.py -v
```

期望:3 passed(1 图端到端 + 2 路由)。若图测试断言需微调,以事件流实际形状为准。

- [ ] **Step 6: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/agents/routes.py backend/app/agents/graph.py backend/tests/fake_model.py backend/tests/test_agents_graph.py
git commit -m "feat: add langgraph supervisor graph with 4 react agents"
```

---

### Task 3: SSE /chat/agent + 持久化 + task_runs 可观测 + 迁移

**Files:**
- Modify: `backend/app/models/task_run.py`(加 user_id / conv_id)
- Create: Alembic 迁移(autogenerate,`alembic revision --autogenerate -m "add user_id conv_id to task_runs"`)
- Create: `backend/app/schemas/agent.py`
- Create: `backend/app/services/agent_service.py`
- Create: `backend/app/api/agent_chat.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_agent_chat.py`

**Interfaces:**
- `POST /api/v1/chat/agent` → `text/event-stream`(SSE)
  - Request:`AgentChatRequest{kb_id, question, conversation_id?, route?}`(route 为空则由 supervisor 分类)
  - Events:`{type: route|node|token|tool|tool_result|answer|sources|done|error}`
- `GET /api/v1/task_runs` → 当前用户运行列表
- `GET /api/v1/task_runs/{run_id}` → 单次运行详情(含 trace)
- 流程:校验 KB → 建/复会话 → create TaskRun(running)→ 图流式执行 → 持久化 user/assistant 消息(sources JSONB)→ update TaskRun(success/failed)

- [ ] **Step 1: 写 SSE 测试(先失败)**

创建 `backend/tests/test_agent_chat.py`:

```python
import json

import app.services.agent_service as agent_svc
import app.services.ingestion_service as ing
from langchain_core.messages import AIMessage

import app.agents.graph as agents_graph
from app.rag.embeddings import fake_embed_texts
from app.rag.vector_store import QdrantVectorStore
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

    llm = FakeToolCallingModel([
        AIMessage(content="rag"),
        AIMessage(content="", tool_calls=[{
            "name": "knowledge_search", "args": {"query": "多智能体"},
            "id": "call_1", "type": "tool_call",
        }]),
        AIMessage(content="DocAgent 是[1]多智能体知识库问答平台。"),
    ])
    monkeypatch.setattr(agent_svc, "_make_chat_llm", lambda: llm)


def _setup(client):
    client.post("/api/v1/auth/register", json={"email": "a5@test.com", "password": "password123"})
    tok = client.post("/api/v1/auth/login", json={"email": "a5@test.com", "password": "password123"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    kb_id = client.post("/api/v1/knowledge_bases", json={"name": "agent库"}, headers=h).json()["id"]
    client.post(f"/api/v1/knowledge_bases/{kb_id}/documents", files={"file": ("r.md", DOC_BYTES)}, headers=h)
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
    with client.stream("POST", "/api/v1/chat/agent",
                       json={"kb_id": kb_id, "question": "什么是多智能体?"},
                       headers=h) as resp:
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/event-stream")
        events = _collect_sse(resp)

    types = [e["type"] for e in events]
    assert "route" in types and events[[t for t in types].index("route")]["route"] == "rag"
    assert "node" in types
    assert "token" in types
    assert "tool" in types  # knowledge_search 被调用
    assert "answer" in types
    ans = next(e for e in events if e["type"] == "answer")["content"]
    assert "DocAgent" in ans
    assert "done" in types

    # 持久化:会话 + 消息 + sources
    conv_id = events[-1].get("conversation_id")
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
    with client.stream("POST", "/api/v1/chat/agent",
                       json={"kb_id": kb_id, "question": "随便聊聊", "route": "utility"},
                       headers=h) as resp:
        events = _collect_sse(resp)
    types = [e["type"] for e in events]
    assert "route" in types  # 直接指定路由,不走分类
    assert any(e["type"] == "done" for e in events)


def test_agent_chat_requires_auth(client):
    with client.stream("POST", "/api/v1/chat/agent", json={"kb_id": 1, "question": "hi"}) as resp:
        assert resp.status_code == 401
```

> 说明:`_patch` 里 `agent_svc._make_chat_llm` 返回脚本化 FakeToolCallingModel,整条 SSE 事件流确定可控。`done` 事件携带 `conversation_id`。若 FakeToolCallingModel 的脚本数不足(rag 只调一次工具),循环内第 2 次调用会触底返回"完成",注意脚本条数对齐。

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_agent_chat.py -v
```

期望:FAIL。

- [ ] **Step 3: 迁移 task_runs 加列**

先改模型 `backend/app/models/task_run.py`:

```python
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    conv_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(50))
    ...
```

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
alembic revision --autogenerate -m "add user_id conv_id to task_runs"
alembic upgrade head
```

> autogenerate 只会比对当前 dev DB head;确认迁移文件只含两列新增。

- [ ] **Step 4: 写 schema**

创建 `backend/app/schemas/agent.py`:

```python
from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    kb_id: int
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None
    route: str | None = Field(default=None, pattern="^(rag|summary|compare|utility)$")
```

- [ ] **Step 5: 写 agent_service.py**

创建 `backend/app/services/agent_service.py`:

```python
from datetime import datetime, timezone
from typing import Any, Generator

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.graph import build_graph, run
from app.agents.llm import get_chat_llm
from app.agents.routes import ROUTES
from app.agents.tools import AgentContext, build_tools
from app.core.config import get_settings
from app.models import Conversation, Document, Message, TaskRun, User
from app.rag.chat_provider import ChatProvider  # noqa: F401  (类型一致性)
from app.rag.embeddings import SiliconFlowEmbeddingProvider
from app.rag.reranker import SiliconFlowReranker
from app.rag.vector_store import QdrantVectorStore
from app.schemas.agent import AgentChatRequest


def _make_vector_store(kb_id: int) -> QdrantVectorStore:
    return QdrantVectorStore(get_settings().QDRANT_COLLECTION, SiliconFlowEmbeddingProvider())


def _make_reranker() -> SiliconFlowReranker:
    return SiliconFlowReranker()


def _make_chat_llm():
    return get_chat_llm()


def _get_owned_kb(db: Session, user: User, kb_id: int):
    from app.models import KnowledgeBase

    kb = db.get(KnowledgeBase, kb_id)
    if kb is None or kb.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    return kb


def _get_owned_conversation(db: Session, user: User, conv_id: int) -> Conversation:
    conv = db.get(Conversation, conv_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv


def stream_agent_chat(
    db: Session, user: User, payload: AgentChatRequest
) -> Generator[dict[str, Any], None, None]:
    """SSE 事件生成器:route/node/token/tool/answer/sources/done/error。"""
    conv: Conversation | None = None
    run_row: TaskRun | None = None
    try:
        kb = _get_owned_kb(db, user, payload.kb_id)
        if payload.conversation_id:
            conv = _get_owned_conversation(db, user, payload.conversation_id)
            if conv.kb_id != kb.id:
                raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                    detail="Conversation belongs to another knowledge base")
        else:
            conv = Conversation(user_id=user.id, kb_id=kb.id, title=payload.question[:30])
            db.add(conv)
            db.commit()
            db.refresh(conv)

        ctx = AgentContext(
            db=db, user=user, kb=kb,
            store_factory=_make_vector_store,
            reranker_factory=_make_reranker,
        )
        tools_by_agent = {
            name: build_tools(ctx) for name in ROUTES
        }
        graph = build_graph(_make_chat_llm(), tools_by_agent)
        thread_id = f"conv_{conv.id}"

        run_row = TaskRun(
            type="agent", status="running", user_id=user.id, conv_id=conv.id,
            trace={"route": payload.route, "thread_id": thread_id, "events": []},
        )
        db.add(run_row)
        db.commit()
        db.refresh(run_row)

        answer_parts: list[str] = []
        for ev in run(graph, payload.question, thread_id, payload.route):
            if ev["type"] == "token":
                answer_parts.append(ev["content"])
            elif ev["type"] == "answer":
                answer_parts.append(ev["content"])
            run_row.trace["events"].append(ev)  # type: ignore[index]
            db.add(run_row)
            yield ev

        answer = "".join(answer_parts)
        sources = ctx.collected_sources
        yield {"type": "sources", "sources": sources}
        yield {"type": "done", "conversation_id": conv.id, "answer": answer}

        db.add(Message(conv_id=conv.id, role="user", content=payload.question))
        db.add(Message(
            conv_id=conv.id, role="assistant", content=answer,
            sources=sources or None, agent_type=f"agent:{payload.route or 'auto'}",
        ))
        run_row.status = "success"
        run_row.finished_at = datetime.now(timezone.utc)
        run_row.trace["route"] = payload.route or "auto"
        db.commit()
    except Exception as e:  # noqa: BLE001
        if run_row is not None:
            run_row.status = "failed"
            run_row.error = f"{type(e).__name__}: {e}"
            run_row.finished_at = datetime.now(timezone.utc)
            db.commit()
        yield {"type": "error", "message": str(e)}


def list_task_runs(db: Session, user: User) -> list[TaskRun]:
    return list(db.execute(
        select(TaskRun).where(TaskRun.user_id == user.id).order_by(TaskRun.id.desc())
    ).scalars())


def get_task_run(db: Session, user: User, run_id: int) -> TaskRun:
    run = db.get(TaskRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task run not found")
    return run
```

> 关键:`run_row.trace["events"]` 就地累计,逐步提交 —— 中断也能看到跑到哪。注意 `trace` 是 JSONB dict,trace["events"] 列表追加即可。

- [ ] **Step 6: 写 api/agent_chat.py**

创建 `backend/app/api/agent_chat.py`:

```python
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.agent import AgentChatRequest
from app.services import agent_service

router = APIRouter(tags=["agent"])


@router.post("/chat/agent")
def chat_agent(
    payload: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    def gen():
        for ev in agent_service.stream_agent_chat(db, current_user, payload):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/task_runs")
def list_runs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return agent_service.list_task_runs(db, current_user)


@router.get("/task_runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return agent_service.get_task_run(db, current_user, run_id)
```

- [ ] **Step 7: main.py 挂载**

编辑 `backend/app/main.py`,import + 挂载 `agent_chat_router`(prefix=API_V1_PREFIX)。

- [ ] **Step 8: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_agent_chat.py -v
```

期望:3 passed。

- [ ] **Step 9: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/models/task_run.py backend/alembic/ backend/app/schemas/agent.py backend/app/services/agent_service.py backend/app/api/agent_chat.py backend/app/main.py backend/tests/test_agent_chat.py
git commit -m "feat: add SSE agent chat with task run observability"
```

---

### Task 4: D5 收尾 —— 全量验证 + 真实冒烟

**Files:** 无新增(验证与收尾)

- [ ] **Step 1: 全量测试**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest -v
```

期望:全部 PASS(D1-D4 51 + D5 约 11)。

- [ ] **Step 2: 真实链路冒烟(用 .env 真实 key)**

写临时 `tmp_d5_smoke.py`(用后即删):TestClient 建库 + 上传 md → `client.stream("POST", /chat/agent)` 收集 SSE → 断言出现 route/node/token/tool/answer/done 事件、answer 非空、sources 非空 → 打印回答 → 检查 task_runs 有 success 记录 → 清理(消息/会话/文档/KB/用户 + QDrant 清空)。

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
PYTHONPATH=/home/sjx_0/project/shixi/backend python ../tmp_d5_smoke.py
```

> 真实链路用真 deepseek-v4-flash 做 supervisor 分类 + ReAct;建议冒烟一条"对比"路由问题,演示工具调用链。耗时较长(每 agent 多轮 LLM)。

- [ ] **Step 3: 检查工作区**

```bash
cd /home/sjx_0/project/shixi
git status
git log --oneline -10
```

期望:工作区干净;log 显示 D5 的 4 个 commit。

- [ ] **Step 4: 收尾提交(若有遗漏)**

```bash
cd /home/sjx_0/project/shixi
git add -A
git commit -m "chore: complete D5 agent orchestration milestone" || echo "无待提交改动"
```
