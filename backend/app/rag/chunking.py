import hashlib
from dataclasses import dataclass, field
from typing import Any

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

# 中文适配分隔符:优先段落与句读,避免英文默认把中文切碎
_CHINESE_SEPARATORS = ["\n\n", "\n", "。", "；", ",", "，", " ", ""]


@dataclass
class ChunkRecord:
    index: int
    content: str
    char_count: int
    hash: str
    meta: dict[str, Any] = field(default_factory=dict)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_document(
    text: str,
    strategy: str,
    chunk_size: int,
    chunk_overlap: int,
    source: dict,
) -> list[ChunkRecord]:
    """按知识库配置的策略分块,并计算每块 hash(幂等去重用)。"""
    if strategy == "recursive":
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=_CHINESE_SEPARATORS,
        )
        raw_chunks = splitter.split_text(text)
    elif strategy == "markdown_header":
        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "h1"),
                ("##", "h2"),
                ("###", "h3"),
            ],
            strip_headers=False,  # 保留标题拼进 chunk 内容,提升召回上下文完整度
        )
        sections = header_splitter.split_text(text)
        # 标题级切分后,再按 chunk_size 做递归字符切分(标题拼进正文保留上下文)
        recursive = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=_CHINESE_SEPARATORS,
        )
        raw_chunks = [c.page_content for c in recursive.split_documents(sections)]
    else:
        raise ValueError(f"Unsupported chunk strategy: {strategy}")

    records: list[ChunkRecord] = []
    for i, content in enumerate(raw_chunks):
        content = content.strip()
        if not content:
            continue
        records.append(
            ChunkRecord(
                index=i,
                content=content,
                char_count=len(content),
                hash=_sha256(content),
                meta={**source, "chunk_index": i},
            )
        )
    return records
