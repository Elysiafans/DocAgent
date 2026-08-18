"""稀疏向量工具。

关键:token 到 index 的映射必须**跨进程稳定**。
D3 早期用 Python 内建 `hash()`,而 str 的 hash 带进程随机盐(PYTHONHASHSEED),
导致写入进程与检索进程产出的稀疏向量不一致、混合检索失效。
这里改用 zlib.crc32,保证存储时与查询时生成完全相同的 index。
"""

import re
import zlib

_CJK_RE = re.compile(r"[一-鿿]")
_SEP_RE = re.compile(r"[\s。，,；;！？!?、()（）【】\[\]\"'：:　]+")


def tokenize(text: str) -> list[str]:
    """分词:空白/标点切分;含中文的 token 再补字符二元组,提升 BM25 对中文的召回。"""
    raw = [t for t in _SEP_RE.split(text) if t]
    tokens: list[str] = []
    for tok in raw:
        if _CJK_RE.search(tok) and len(tok) > 1:
            tokens.append(tok)
            tokens.extend(tok[i : i + 2] for i in range(len(tok) - 1))
        else:
            tokens.append(tok)
    return tokens


def build_sparse_vector(text: str) -> tuple[list[int], list[float]]:
    """token -> 稳定 index(zlib.crc32)。返回升序去重 indices 与对应词频。"""
    counts: dict[int, float] = {}
    for tok in tokenize(text):
        idx = zlib.crc32(tok.encode("utf-8"))
        counts[idx] = counts.get(idx, 0) + 1.0
    indices = sorted(counts)
    return indices, [counts[i] for i in indices]
