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
