import hashlib
from typing import Protocol

import httpx

from app.core.config import get_settings


class EmbeddingProvider(Protocol):
    """嵌入 Provider 抽象:可切换 SiliconFlow / 其他,测试注入 fake。"""

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


def fake_embed_texts(texts: list[str], dim: int = 8) -> list[list[float]]:
    """确定性伪嵌入(测试/本地冒烟用):同一文本永远同向量。"""
    return [
        [
            int(hashlib.sha256(t.encode()).hexdigest()[i : i + 2], 16) / 255.0
            for i in range(dim)
        ]
        for t in texts
    ]


class SiliconFlowEmbeddingProvider:
    """SiliconFlow bge-m3 嵌入,OpenAI 兼容 /embeddings。带批处理与简单重试。"""

    def __init__(self, timeout: float = 30.0):
        s = get_settings()
        self.model = s.EMBEDDING_MODEL
        self.batch_size = s.EMBEDDING_BATCH_SIZE
        self._client = httpx.Client(
            base_url=s.SILICONFLOW_BASE_URL,
            headers={"Authorization": f"Bearer {s.SILICONFLOW_API_KEY}"},
            timeout=timeout,
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            results.extend(self._embed_batch(batch))
        return results

    def _embed_batch(self, batch: list[str], retries: int = 2) -> list[list[float]]:
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = self._client.post(
                    "/embeddings",
                    json={"model": self.model, "input": batch},
                )
                resp.raise_for_status()
                data = resp.json()["data"]
                data.sort(key=lambda d: d["index"])
                return [d["embedding"] for d in data]
            except Exception as e:  # noqa: BLE001
                last_err = e
                if attempt == retries:
                    raise RuntimeError(
                        f"embedding failed after {retries} retries"
                    ) from last_err
        raise RuntimeError("unreachable")  # pragma: no cover
