"""MCP 工具规格:把 DocAgent 能力暴露为 MCP `tools/list` / `tools/call`。

工具 call 签名统一为 `call(ctx, arguments) -> str`。KB 相关工具通过
`ctx_factory(kb_id)` 按需重建上下文(归属校验在 API 层完成),实现多知识库支持。
"""
from __future__ import annotations

import ast

from app.agents.tools import _doc_names, _safe_eval, _web_search_impl
from app.rag.retrieval import assemble_context, retrieve


def _kb_search_call(ctx, arguments) -> str:
    query = arguments["query"]
    top_k = int(arguments.get("top_k", 5))
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


def _compare_call(ctx, arguments) -> str:
    query = arguments["query"]
    topics = arguments.get("topics") or [query]
    store = ctx.store_factory(ctx.kb.id)
    reranker = ctx.reranker_factory() if ctx.reranker_factory else None
    sections: list[str] = []
    for topic in topics:
        chunks = retrieve(store, reranker, topic, ctx.kb.id, top_k=10, top_n=3)
        if not chunks:
            continue
        doc_names = _doc_names(ctx, {c.doc_id for c in chunks})
        sections.append(f"【{topic}】\n{assemble_context(chunks, doc_names)}")
    return "\n\n".join(sections) or "未检索到相关内容"


def _calculator_call(ctx, arguments) -> str:
    expr = arguments["expr"]
    try:
        return str(_safe_eval(ast.parse(expr, mode="eval")))
    except (ValueError, SyntaxError, ZeroDivisionError):
        return "表达式不支持或非法"


def _web_call(ctx, arguments) -> str:
    return _web_search_impl(arguments["query"])


def mcp_tool_specs() -> list[dict]:
    """静态工具规格(不含上下文);`call` 在执行时由 McpServer 注入 ctx。"""
    return [
        {
            "name": "knowledge_search",
            "description": "在指定知识库(kb_id)做混合检索,返回带 [编号] 的片段与来源。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "kb_id": {"type": "integer"},
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["kb_id", "query"],
            },
            "needs_kb": True,
            "call": _kb_search_call,
        },
        {
            "name": "compare_documents",
            "description": "在指定知识库对多个主题分别检索并汇总,给出多角度对比。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "kb_id": {"type": "integer"},
                    "query": {"type": "string"},
                    "topics": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["kb_id", "query"],
            },
            "needs_kb": True,
            "call": _compare_call,
        },
        {
            "name": "calculator",
            "description": "安全计算算术表达式(支持 + - * / % ** 与括号),输入形如 (1+2)*3。",
            "inputSchema": {
                "type": "object",
                "properties": {"expr": {"type": "string"}},
                "required": ["expr"],
            },
            "needs_kb": False,
            "call": _calculator_call,
        },
        {
            "name": "web_search",
            "description": "联网搜索最新信息(DuckDuckGo),返回前几条标题与摘要。",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            "needs_kb": False,
            "call": _web_call,
        },
    ]
