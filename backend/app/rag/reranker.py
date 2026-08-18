from typing import Protocol

import httpx

from app.core.config import get_settings


class Reranker(Protocol):
    """重排抽象:输入 query + 候选文档,返回按相关度降序的 (index, score) 列表(取 top_n)。"""

    def __call__(
        self, query: str, documents: list[str], top_n: int
    ) -> list[tuple[int, float]]: ...


def fake_rerank(
    query: str, documents: list[str], top_n: int
) -> list[tuple[int, float]]:
    """伪重排:按 query 字符在文档中出现次数打分(测试用,确定性)。"""

    def score(doc: str) -> float:
        overlap = sum(1 for ch in query if ch in doc)
        # 完全匹配/包含 额外加权,区分"苹果"与"苹果香蕉"
        if doc == query:
            return float(overlap) + 1.0
        if query in doc:
            return float(overlap) + 0.5
        return float(overlap)

    ranked = sorted(
        ((i, score(d)) for i, d in enumerate(documents)),
        key=lambda x: x[1],
        reverse=True,
    )
    return ranked[:top_n]


class SiliconFlowReranker:
    """SiliconFlow bge-reranker-v2-m3,POST /rerank。"""

    def __init__(self, timeout: float = 30.0):
        s = get_settings()
        self.model = s.RERANK_MODEL
        self._client = httpx.Client(
            base_url=s.SILICONFLOW_BASE_URL,
            headers={"Authorization": f"Bearer {s.SILICONFLOW_API_KEY}"},
            timeout=timeout,
        )

    def rerank(
        self, query: str, documents: list[str], top_n: int
    ) -> list[tuple[int, float]]:
        resp = self._client.post(
            "/rerank",
            json={"model": self.model, "query": query, "documents": documents},
        )
        resp.raise_for_status()
        results = sorted(
            resp.json()["results"],
            key=lambda r: r["relevance_score"],
            reverse=True,
        )
        return [(r["index"], float(r["relevance_score"])) for r in results[:top_n]]

    def __call__(
        self, query: str, documents: list[str], top_n: int
    ) -> list[tuple[int, float]]:
        """让实例可作为 Reranker callable 传给 retrieve()。"""
        return self.rerank(query, documents, top_n)
