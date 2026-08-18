import ast
import operator
from dataclasses import dataclass, field
from typing import Any, Callable

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, KnowledgeBase, User
from app.protocols import skills as skills_registry
from app.rag.reranker import Reranker
from app.rag.retrieval import assemble_context, retrieve
from app.rag.vector_store import QdrantVectorStore


@dataclass
class AgentContext:
    """每次 agent 运行共享的上下文:持有库归属 + 注入式 Provider 工厂。"""

    db: Session | None
    user: User | None
    kb: KnowledgeBase
    store_factory: Callable[[int], QdrantVectorStore]
    reranker_factory: Callable[[], Reranker | None] | None = None
    collected_sources: list[dict[str, Any]] = field(default_factory=list)


# ---- 安全计算:AST 白名单求值,杜绝 eval/任意代码 ----
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
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
            f"- {r.get('title', '')}: {r.get('body', '')[:120]}" for r in results
        )
    except Exception as e:  # noqa: BLE001
        return f"联网搜索暂不可用(离线/超时):{type(e).__name__}"


def _doc_names(ctx: AgentContext, doc_ids: set[int]) -> dict[int, str]:
    if not doc_ids or ctx.db is None:
        return {}
    return {
        d.id: d.name
        for d in ctx.db.execute(
            select(Document).where(Document.id.in_(doc_ids))
        ).scalars()
    }


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
        doc_names = _doc_names(ctx, {c.doc_id for c in chunks})
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
        """安全计算算术表达式(支持 + - * / % ** 与括号),输入形如 "(1+2)*3"。"""
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
    def load_skill(skill_name: str) -> str:
        """加载一个 Agent Skill(SKILL.md 技能说明),返回其内容供遵循执行。"""
        try:
            return skills_registry.load_skill(skill_name)
        except KeyError:
            available = ", ".join(skills_registry.list_skill_names())
            return f"未找到技能 {skill_name};可用技能: {available or '无'}"

    @tool
    def compare_documents(query: str, topics: list[str] | None = None) -> str:
        """对比分析:对每个主题分别检索并汇总,给出多角度对比结果。"""
        store = ctx.store_factory(ctx.kb.id)
        reranker = ctx.reranker_factory() if ctx.reranker_factory else None
        sections: list[str] = []
        seen: set[int] = set()
        for topic in (topics or [query]):
            chunks = retrieve(
                store, reranker, topic, ctx.kb.id, top_k=10, top_n=3
            )
            if not chunks:
                continue
            doc_names = _doc_names(ctx, {c.doc_id for c in chunks})
            ctx.collected_sources.extend(
                {
                    "doc_id": c.doc_id,
                    "doc_name": doc_names.get(c.doc_id),
                    "chunk_index": c.chunk_index,
                    "content": c.content,
                    "score": round(c.score, 4),
                }
                for c in chunks
                if c.doc_id not in seen
            )
            seen.update(c.doc_id for c in chunks)
            sections.append(f"【{topic}】\n{assemble_context(chunks, doc_names)}")
        return "\n\n".join(sections) or "未检索到相关内容"

    return [
        knowledge_search,
        calculator,
        web_search,
        compare_documents,
        load_skill,
    ]
