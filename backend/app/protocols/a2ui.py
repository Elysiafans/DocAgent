"""A2UI(Agent2User)卡片渲染:把 agent 消息渲染为结构化 UI 卡片。

卡片 JSON 供前端(D7)直接渲染:header + 文本 parts + 可选 sources 子卡片。
"""
from __future__ import annotations

from typing import Any


def render_message_card(message, sources: list[dict] | None = None) -> dict:
    """把一条 agent 消息渲染为 A2UI 卡片。message 需有 id / content / agent_type。"""
    sources = sources or []
    card: dict[str, Any] = {
        "cardId": f"msg-{message.id}",
        "type": "message",
        "header": {
            "title": "DocAgent 回答",
            "subtitle": getattr(message, "agent_type", None) or "agent",
        },
        "parts": [{"kind": "text", "text": message.content}],
        "children": [],
    }
    if sources:
        card["children"].append({"type": "sources", "sources": sources})
    return card
