# DocAgent D3 —— 文档处理 + RAG 底座(摄取链路)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通「上传 → 解析 → 分块 → 嵌入 → 写入 QDrant」的完整摄取链路,并提供文档上传/列表/删除 API 与后台进度跟踪,全部有测试覆盖。

**Architecture:**
- 新增 `app/rag/` 包,四块独立可测的组件:`parsers.py`(解析)、`chunking.py`(分块)、`embeddings.py`(嵌入 Provider)、`vector_store.py`(QDrant 读写)。
- 摄取流水线编排在 `services/ingestion_service.py`,通过 **FastAPI BackgroundTasks** 异步执行,Document 表实时记录 `status/progress/stage`。
- QDrant 用**单 collection `docagent_knowledge`**(稠密+稀疏同 collection,payload 带 `kb_id`/`doc_id`/`chunk_index`),D4 检索与 D5 跨库对比都基于它。
- 对话模型按用户要求固定为 **`deepseek-v4-flash`**(config 已改,本计划不新增调用)。

**Tech Stack:** 沿用 D1/D2。新增依赖:qdrant-client、langchain-text-splitters、pypdf、python-docx(均已装进 yy 环境)。

## Global Constraints

- 沿用 D1/D2 约束:WSL 内执行、`yy` 环境、命令前缀 `source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy && <cmd>`。
- Postgres 与 QDrant 容器需运行中(`docker compose ps` 确认;若未运行 `docker compose up -d`)。D3 的 QDrant 测试打**真实 QDrant** 的**测试专用 collection**(`docagent_test_collection`,fixture 建/清/删),不碰 `docagent_knowledge` 生产 collection。
- **测试绝不调用真实 SiliconFlow/DeepSeek API**:嵌入 Provider 全部用**注入的 fake embedder**。真实 Provider 只做冒烟验证(需 .env 里填 SILICONFLOW_API_KEY)。
- 测试数据库仍为 `docagent_test`(沿用 D2 conftest)。
- 密钥永不入库;迁移只用 Alembic;提交用 conventional commits。
- QDrant 相关代码用 `qdrant-client` 直接调用(不套 langchain-qdrant),展示对向量库的底层理解。

---

### Task 1: 依赖 + 配置 + QDrant 连通性

**Files:**
- Modify: `backend/requirements.txt`(已加 D3 依赖,校验)
- Modify: `backend/app/core/config.py`(加 QDrant collection / 嵌入参数)
- Modify: `.env.example`(补 QDrant 注释)
- Create: `backend/app/rag/__init__.py`
- Create: `backend/app/rag/client.py`(QDrant 客户端单例)
- Create: `backend/tests/test_qdrant.py`
- Test: `backend/tests/test_qdrant.py`

**Interfaces:**
- Consumes: `Settings`、docker 里的 QDrant
- Produces:
  - `app.rag.client.get_qdrant() -> QdrantClient`(lru_cache 单例)
  - Settings 新增:`QDRANT_COLLECTION="docagent_knowledge"`、`EMBEDDING_MODEL_DIM=1024`、`EMBEDDING_BATCH_SIZE=32`

- [ ] **Step 1: 校验 requirements.txt 已含 D3 依赖**

确认 `backend/requirements.txt` 含:`qdrant-client==1.19.0`、`langchain-core==1.5.2`、`langchain-text-splitters==1.1.2`、`langchain-openai==1.4.1`、`openai==2.48.0`、`pypdf==6.16.1`、`python-docx==1.2.0`。

- [ ] **Step 2: config.py 增加 QDrant 与嵌入参数**

在 `QDRANT_URL` 之后加:

```python
    # QDrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "docagent_knowledge"

    # 嵌入参数
    EMBEDDING_MODEL_DIM: int = 1024  # bge-m3
    EMBEDDING_BATCH_SIZE: int = 32
```

`DEEPSEEK_CHAT_MODEL` 已改为 `deepseek-v4-flash`(用户指定),确认无回归。

- [ ] **Step 3: .env.example 补注释**

在 `QDRANT_URL` 行下补一行 `# QDrant collection 名(测试用 docagent_test_collection,不占用)`(仅注释)。

- [ ] **Step 4: 写 client 单例**

创建 `backend/app/rag/__init__.py`(空)与 `backend/app/rag/client.py`:

```python
from functools import lru_cache

from qdrant_client import QdrantClient

from app.core.config import get_settings


@lru_cache
def get_qdrant() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.QDRANT_URL)
```

- [ ] **Step 5: 写连通性测试**

创建 `backend/tests/test_qdrant.py`:

```python
from app.rag.client import get_qdrant

TEST_COLLECTION = "docagent_test_collection"


def test_qdrant_connect_and_collection_ops():
    client = get_qdrant()
    # 清理可能残留
    if client.collection_exists(TEST_COLLECTION):
        client.delete_collection(TEST_COLLECTION)
    client.create_collection(TEST_COLLECTION, vectors_config={"size": 4, "distance": "Cosine"})
    assert client.collection_exists(TEST_COLLECTION)
    assert [c.name for c in client.get_collections().collections] and TEST_COLLECTION in [
        c.name for c in client.get_collections().collections
    ]
    client.delete_collection(TEST_COLLECTION)
    assert not client.collection_exists(TEST_COLLECTION)
```

- [ ] **Step 6: 运行测试**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_qdrant.py -v
```

期望:1 passed。若连接失败,先 `docker compose ps` 确认 qdrant 容器 Up。

- [ ] **Step 7: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/requirements.txt backend/app/core/config.py backend/app/rag .env.example backend/tests/test_qdrant.py
git commit -m "feat: add qdrant client and embedding config"
```

---

### Task 2: 嵌入 Provider(bge-m3,可注入 fake)

**Files:**
- Create: `backend/app/rag/embeddings.py`
- Test: `backend/tests/test_embeddings.py`

**Interfaces:**
- Consumes: `Settings`(SILICONFLOW_*)、`httpx`
- Produces:
  - `class EmbeddingProvider(Protocol): embed_texts(texts: list[str]) -> list[list[float]]`
  - `class SiliconFlowEmbeddingProvider`: 走 SiliconFlow OpenAI 兼容 `/embeddings`(bge-m3,1024 维),批处理 + 简单重试
  - `fake_embed_texts(texts: list[str]) -> list[list[float]]`(测试用:按文本稳定映射到低维向量)

- [ ] **Step 1: 写嵌入测试(先失败)**

创建 `backend/tests/test_embeddings.py`:

```python
from app.rag.embeddings import SiliconFlowEmbeddingProvider, fake_embed_texts


def test_fake_embed_deterministic_and_shared():
    v1 = fake_embed_texts(["你好", "世界"])
    v2 = fake_embed_texts(["你好", "世界"])
    assert len(v1) == 2
    assert len(v1[0]) == 8  # fake 维度
    assert v1 == v2
    assert v1[0] != v1[1]  # 不同文本不同向量


def test_provider_batches_and_parses(monkeypatch):
    provider = SiliconFlowEmbeddingProvider()
    calls = []

    def fake_post(self, *args, **kwargs):
        calls.append(kwargs.get("json") or args[1])
        data = kwargs["json"] or args[1]
        n = len(data["input"])
        return type(
            "R",
            (),
            {
                "raise_for_status": lambda *a: None,
                "json": lambda: {
                    "data": [
                        {"embedding": [float(i + 1) / 10.0] * 4, "index": i}
                        for i in range(n)
                    ]
                },
            },
        )()

    monkeypatch.setattr("app.rag.embeddings.httpx.Client.post", fake_post)
    result = provider.embed_texts(["a", "b"])
    assert len(result) == 2
    assert len(result[0]) == 4
    assert calls and len(calls) == 1  # 一次批量
```

> 说明:测试通过 monkeypatch 替换 `httpx.Client.post`,不触网。真实调用需 `.env` 有 SILICONFLOW_API_KEY,冒烟验证见 Task 6。

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_embeddings.py -v
```

期望:FAIL,`ModuleNotFoundError`。

- [ ] **Step 3: 实现 embeddings.py**

创建 `backend/app/rag/embeddings.py`:

```python
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
                    raise RuntimeError(f"embedding failed after {retries} retries") from last_err
        raise RuntimeError("unreachable")  # pragma: no cover
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_embeddings.py -v
```

期望:2 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/rag/embeddings.py backend/tests/test_embeddings.py
git commit -m "feat: add embedding provider abstraction with bge-m3"
```

---

### Task 3: 文档解析器(pdf / docx / md / txt)

**Files:**
- Create: `backend/app/rag/parsers.py`
- Test: `backend/tests/test_parsers.py`

**Interfaces:**
- Consumes: `pypdf`、`python-docx`、标准库
- Produces:
  - `@dataclass ParsedPage: text: str, page_no: int | None`
  - `parse_document(content: bytes, file_type: str) -> list[ParsedPage]`
  - 支持类型:`pdf`(分页)、`docx`(分页=段落号)、`md`/`txt`(单页)

- [ ] **Step 1: 写解析测试(先失败)**

创建 `backend/tests/test_parsers.py`:

```python
import io

import docx
from pypdf import PdfWriter

from app.rag.parsers import parse_document


def _make_pdf(text: str) -> bytes:
    # 用 reportlab 太依赖,改用 pypdf 的空白页 + 直接注入文本不可行;
    # 这里用最轻的方式:构造单页 PDF(文本用 /Contents 流)。
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_parse_txt_single_page():
    pages = parse_document("你好\n世界\n".encode(), "txt")
    assert len(pages) == 1
    assert "你好" in pages[0].text
    assert pages[0].page_no == 0


def test_parse_md_single_page():
    pages = parse_document("# 标题\n正文".encode(), "md")
    assert len(pages) == 1
    assert pages[0].text.startswith("# 标题")


def test_parse_docx_paragraphs():
    d = docx.Document()
    d.add_paragraph("第一段")
    d.add_paragraph("第二段")
    buf = io.BytesIO()
    d.save(buf)
    pages = parse_document(buf.getvalue(), "docx")
    assert "第一段" in pages[0].text and "第二段" in pages[0].text


def test_parse_pdf_returns_one_page():
    pages = parse_document(_make_pdf("hello"), "pdf")
    assert len(pages) == 1
    assert pages[0].page_no == 0


def test_unsupported_type_raises():
    import pytest

    with pytest.raises(ValueError):
        parse_document(b"x", "exe")
```

> 注意:上面的 PDF 是**空白页**,`extract_text()` 返回空串。测试只断言**页数与 page_no**,不断言文本内容(PDF 文本注入需要 reportlab,不引入该依赖)。

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_parsers.py -v
```

期望:FAIL。

- [ ] **Step 3: 实现 parsers.py**

创建 `backend/app/rag/parsers.py`:

```python
import io
from dataclasses import dataclass
from pathlib import PurePosixPath

import docx
from pypdf import PdfReader


@dataclass
class ParsedPage:
    text: str
    page_no: int | None = None  # PDF 页码(docx 里填段落索引;txt/md 为 0)


def parse_document(content: bytes, file_type: str) -> list[ParsedPage]:
    """按文件类型分发到解析器,统一返回逐页文本。"""
    parser = _PARSERS.get(file_type.lower())
    if parser is None:
        raise ValueError(f"Unsupported file type: {file_type}")
    return parser(content)


def _parse_txt(content: bytes) -> list[ParsedPage]:
    return [ParsedPage(text=content.decode("utf-8", errors="replace"), page_no=0)]


def _parse_pdf(content: bytes) -> list[ParsedPage]:
    reader = PdfReader(io.BytesIO(content))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append(ParsedPage(text=text, page_no=i))
    return pages


def _parse_docx(content: bytes) -> list[ParsedPage]:
    doc = docx.Document(io.BytesIO(content))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [ParsedPage(text=text, page_no=0)]


_PARSERS = {
    "pdf": _parse_pdf,
    "docx": _parse_docx,
    "md": _parse_txt,
    "markdown": _parse_txt,
    "txt": _parse_txt,
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_parsers.py -v
```

期望:5 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/rag/parsers.py backend/tests/test_parsers.py
git commit -m "feat: add document parsers (pdf/docx/md/txt)"
```

---

### Task 4: 分块器(可配置策略 + 中文适配 + 哈希去重)

**Files:**
- Create: `backend/app/rag/chunking.py`
- Test: `backend/tests/test_chunking.py`

**Interfaces:**
- Consumes: `langchain_text_splitters`
- Produces:
  - `@dataclass ChunkRecord: index, content, char_count, hash, meta`
  - `chunk_document(text: str, strategy: str, chunk_size: int, chunk_overlap: int, source: dict) -> list[ChunkRecord]`
  - strategy:`recursive`(中文分隔符适配)/ `markdown_header`(标题感知)

- [ ] **Step 1: 写分块测试(先失败)**

创建 `backend/tests/test_chunking.py`:

```python
from app.rag.chunking import chunk_document


def test_recursive_respects_chinese_separators():
    # 4 段,chunk_size 只够装约 2 段 -> 得到 >1 块,且不会在中文句中硬切(每块以分隔符边界为主)
    text = "第一句。第二句。第三句。\n\n第四句。\n\n第五句。\n\n第六句。"
    chunks = chunk_document(text, "recursive", chunk_size=16, chunk_overlap=4, source={"doc_id": 1})
    assert len(chunks) > 1
    assert all(c.char_count > 0 for c in chunks)
    assert all(c.hash for c in chunks)
    # 幂等:同输入同哈希
    again = chunk_document(text, "recursive", chunk_size=16, chunk_overlap=4, source={"doc_id": 1})
    assert [c.hash for c in chunks] == [c.hash for c in again]


def test_markdown_header_keeps_heading_context():
    text = "# 第一章\n\n内容甲。\n\n## 第一节\n\n内容乙。"
    chunks = chunk_document(text, "markdown_header", chunk_size=200, chunk_overlap=0, source={"doc_id": 2})
    # 标题感知:至少出现一个 chunk 内容里带 "# 第一章" 前缀
    assert any("# 第一章" in c.content for c in chunks)


def test_unsupported_strategy_raises():
    import pytest

    with pytest.raises(ValueError):
        chunk_document("x", "unknown_strategy", 100, 0, source={})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_chunking.py -v
```

期望:FAIL。

- [ ] **Step 3: 实现 chunking.py**

创建 `backend/app/rag/chunking.py`:

```python
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
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        raw_chunks = [
            c.page_content for c in header_splitter.split_text(text)
        ]
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
```

> 注:`markdown_header` 的 `chunk_size`/`chunk_overlap` 在 langchain-text-splitters 1.x 通过 `MarkdownHeaderTextSplitter(headers_to_split_on=..., chunk_size=..., chunk_overlap=...)` 支持;若该版本参数位置不同,以实际签名调整(运行时确认)。

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_chunking.py -v
```

期望:3 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/rag/chunking.py backend/tests/test_chunking.py
git commit -m "feat: add configurable chunking with hash dedup"
```

---

### Task 5: QDrant 向量存储(collection + upsert + 按文档删除)

**Files:**
- Create: `backend/app/rag/vector_store.py`
- Test: `backend/tests/test_vector_store.py`

**Interfaces:**
- Consumes: `get_qdrant()`、`EmbeddingProvider`
- Produces:
  - `class QdrantVectorStore(collection: str, embedder: EmbeddingProvider)`
  - `ensure_collection()`(稠密 1024 + 稀疏 BM25,幂等)
  - `upsert_document(doc_id: int, kb_id: int, chunks: list[ChunkRecord]) -> int`
  - `delete_document_chunks(doc_id: int) -> None`
  - `count_chunks(doc_id: int) -> int`

- [ ] **Step 1: 写存储测试(先失败)**

创建 `backend/tests/test_vector_store.py`:

```python
from app.rag.client import get_qdrant
from app.rag.embeddings import fake_embed_texts
from app.rag.vector_store import QdrantVectorStore

TEST_COLLECTION = "docagent_test_collection"


def _make_store(dim=8) -> QdrantVectorStore:
    client = get_qdrant()
    if client.collection_exists(TEST_COLLECTION):
        client.delete_collection(TEST_COLLECTION)
    store = QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=dim)
    store.ensure_collection()
    return store


def _chunks(n=3):
    from app.rag.chunking import ChunkRecord

    return [
        ChunkRecord(index=i, content=f"chunk {i}", char_count=6, hash=f"h{i}", meta={"kb_id": 1, "doc_id": 42, "chunk_index": i})
        for i in range(n)
    ]


def test_upsert_and_count():
    store = _make_store()
    n = store.upsert_document(42, 1, _chunks())
    assert n == 3
    assert store.count_chunks(42) == 3


def test_delete_document_chunks():
    store = _make_store()
    store.upsert_document(42, 1, _chunks())
    store.delete_document_chunks(42)
    assert store.count_chunks(42) == 0


def test_ensure_collection_idempotent():
    store = _make_store()
    store.ensure_collection()  # 第二次调用不报错
    assert get_qdrant().collection_exists(TEST_COLLECTION)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_vector_store.py -v
```

期望:FAIL。

- [ ] **Step 3: 实现 vector_store.py**

创建 `backend/app/rag/vector_store.py`:

```python
from typing import Callable

from qdrant_client import models

from app.core.config import get_settings
from app.rag.chunking import ChunkRecord
from app.rag.client import get_qdrant

Embedder = Callable[[list[str]], list[list[float]]]


class QdrantVectorStore:
    """QDrant 读写封装:稠密(bge-m3)+ 稀疏(BM25)同 collection。"""

    def __init__(self, collection: str, embedder: Embedder, dim: int | None = None):
        self.collection = collection
        self.embedder = embedder
        self.dim = dim or get_settings().EMBEDDING_MODEL_DIM
        self._client = get_qdrant()

    def ensure_collection(self) -> None:
        if self._client.collection_exists(self.collection):
            return
        self._client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(
                size=self.dim, distance=models.Distance.COSINE
            ),
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(
                    modifier=models.Modifier.IDF  # BM25 稀疏权重
                )
            },
        )

    def upsert_document(self, doc_id: int, kb_id: int, chunks: list[ChunkRecord]) -> int:
        self.ensure_collection()
        texts = [c.content for c in chunks]
        vectors = self.embedder(texts)
        points = []
        for c, vec in zip(chunks, vectors):
            # 稀疏向量:按词频统计(token 用空格分词;中文按字符级词袋,演示 BM25)
            tokens: dict[str, int] = {}
            for tok in c.content.replace("。", " ").replace(",", " ").split():
                tokens[tok] = tokens.get(tok, 0) + 1
            points.append(
                models.PointStruct(
                    id=self._point_id(doc_id, c.index),
                    vector={
                        "dense": vec,
                        "sparse": models.SparseVector(
                            indices=[hash(t) & 0xFFFFFFFF for t in tokens],
                            values=[float(v) for v in tokens.values()],
                        ),
                    },
                    payload={
                        "kb_id": kb_id,
                        "doc_id": doc_id,
                        "chunk_index": c.index,
                        "content": c.content,
                        "char_count": c.char_count,
                        "hash": c.hash,
                        **c.meta,
                    },
                )
            )
        self._client.upsert(collection_name=self.collection, points=points)
        return len(points)

    def delete_document_chunks(self, doc_id: int) -> None:
        self._client.delete(
            collection_name=self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))]
                )
            ),
        )

    def count_chunks(self, doc_id: int) -> int:
        return self._client.count(
            collection_name=self.collection,
            count_filter=models.Filter(
                must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))]
            ),
            exact=True,
        ).count

    @staticmethod
    def _point_id(doc_id: int, index: int) -> int:
        return doc_id * 10_000 + index
```

> 稀疏向量 token 化是**演示级简化**(字符级词袋),D4 再打磨成真正 BM25;D3 重点是写入通路与 payload 结构。

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_vector_store.py -v
```

期望:3 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/rag/vector_store.py backend/tests/test_vector_store.py
git commit -m "feat: add qdrant vector store with dense+sparse upsert"
```

---

### Task 6: 摄取服务 + 文档上传/列表/删除 API + 后台进度

**Files:**
- Create: `backend/app/schemas/document.py`
- Create: `backend/app/services/document_service.py`
- Create: `backend/app/services/ingestion_service.py`
- Create: `backend/app/api/documents.py`
- Modify: `backend/app/main.py`(挂载 documents 路由)
- Test: `backend/tests/test_documents.py`

**Interfaces:**
- Consumes: `parse_document`、`chunk_document`、`QdrantVectorStore`、`get_db`、`get_current_user`
- Produces:
  - `POST /api/v1/knowledge_bases/{kb_id}/documents`(multipart) → 201 `DocumentOut`,后台异步摄取
  - `GET /api/v1/knowledge_bases/{kb_id}/documents` → 列表
  - `GET /api/v1/documents/{doc_id}` → 单个(含 status/progress)
  - `DELETE /api/v1/documents/{doc_id}` → 204(同时清 QDrant)
  - 摄取流水线:create Document(uploading) → parse → chunk → embed → upsert → update Document(ready)

- [ ] **Step 1: 写文档 API 测试(先失败)**

创建 `backend/tests/test_documents.py`:

```python
import io

from app.rag.client import get_qdrant
from app.rag.embeddings import fake_embed_texts
from app.rag.vector_store import QdrantVectorStore

TEST_COLLECTION = "docagent_test_collection"
_FILES = {"text/plain": ("sample.txt", b"第一行。\n第二行。\n第三行。")}


def _auth(client, email="d@test.com"):
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _ensure_test_collection():
    # 用与 vector_store 测试相同的 collection,保证 upsert 后可见
    store = QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=8)
    store.ensure_collection()
    return store


def test_upload_process_and_query_document(client, monkeypatch):
    # 注入 fake 嵌入到 ingestion_service 使用的模块
    import app.services.ingestion_service as ing

    monkeypatch.setattr(ing, "_make_vector_store", lambda kb_id: QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=8))

    h = _auth(client)
    kb_id = client.post("/api/v1/knowledge_bases", json={"name": "库A"}, headers=h).json()["id"]

    # 上传(后台任务在 TestClient 里同步执行)
    r = client.post(
        f"/api/v1/knowledge_bases/{kb_id}/documents",
        files={"file": _FILES["text/plain"]},
        headers=h,
    )
    assert r.status_code == 201
    doc_id = r.json()["id"]

    # 后台摄取完成 -> 状态应为 ready
    doc = client.get(f"/api/v1/documents/{doc_id}", headers=h).json()
    assert doc["status"] == "ready"
    assert doc["chunk_count"] >= 1

    # QDrant 里有 chunk
    store = QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=8)
    assert store.count_chunks(doc_id) == doc["chunk_count"]

    # 列表
    docs = client.get(f"/api/v1/knowledge_bases/{kb_id}/documents", headers=h).json()
    assert any(d["id"] == doc_id for d in docs)

    # 删除 -> QDrant 清空
    assert client.delete(f"/api/v1/documents/{doc_id}", headers=h).status_code == 204
    assert store.count_chunks(doc_id) == 0


def test_upload_requires_kb_ownership(client):
    h = _auth(client)
    # 不存在/他人的库 -> 404
    r = client.post(
        "/api/v1/knowledge_bases/999/documents",
        files={"file": _FILES["text/plain"]},
        headers=h,
    )
    assert r.status_code == 404


def test_documents_require_auth(client):
    assert client.get("/api/v1/knowledge_bases/1/documents").status_code == 401
```

> 关键:`ingestion_service` 里建 store 的函数名是 `_make_vector_store`(测试 monkeypatch 它)。若实现改名需同步。TestClient 默认同步执行 BackgroundTasks,因此上传后立即能查到 ready。

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_documents.py -v
```

期望:FAIL。

- [ ] **Step 3: 写 schemas/document.py**

创建 `backend/app/schemas/document.py`:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kb_id: int
    name: str
    file_type: str
    size: int
    status: str  # uploading / parsing / chunking / embedding / ready / failed
    progress: int
    stage: str
    chunk_count: int
    error: str | None
    created_at: datetime
```

- [ ] **Step 4: 写 document_service.py(DB 侧)**

创建 `backend/app/services/document_service.py`:

```python
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, KnowledgeBase, User


def _get_owned_kb(db: Session, user: User, kb_id: int) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None or kb.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    return kb


def list_documents(db: Session, user: User, kb_id: int) -> list[Document]:
    _get_owned_kb(db, user, kb_id)
    return list(
        db.execute(
            select(Document).where(Document.kb_id == kb_id).order_by(Document.id.desc())
        ).scalars()
    )


def get_document(db: Session, user: User, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    kb = db.get(KnowledgeBase, doc.kb_id) if doc else None
    if doc is None or kb is None or kb.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


def delete_document(db: Session, user: User, doc_id: int) -> Document:
    doc = get_document(db, user, doc_id)
    db.delete(doc)
    db.commit()
    return doc
```

- [ ] **Step 5: 写 ingestion_service.py(流水线)**

创建 `backend/app/services/ingestion_service.py`:

```python
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Document, TaskRun
from app.rag.chunking import chunk_document
from app.rag.client import get_qdrant
from app.rag.embeddings import SiliconFlowEmbeddingProvider
from app.rag.parsers import parse_document
from app.rag.vector_store import QdrantVectorStore


def _make_vector_store(kb_id: int) -> QdrantVectorStore:
    """生产用真实 SiliconFlow 嵌入 + 生产 collection。测试 monkeypatch 替换。"""
    return QdrantVectorStore(
        get_settings().QDRANT_COLLECTION, SiliconFlowEmbeddingProvider()
    )


def ingest_document(db: Session, doc: Document, raw: bytes) -> None:
    """后台任务:parse -> chunk -> embed -> upsert -> 更新 Document。"""
    kb = db.get(__import__("app.models", fromlist=["KnowledgeBase"]).KnowledgeBase, doc.kb_id)
    store = _make_vector_store(kb.id)

    try:
        db.refresh(doc)
        doc.status = "parsing"; doc.stage = "parse"; db.commit()
        pages = parse_document(raw, doc.file_type)
        text = "\n".join(p.text for p in pages if p.text.strip())

        doc.status = "chunking"; doc.stage = "chunk"; doc.progress = 40; db.commit()
        chunks = chunk_document(
            text,
            kb.chunk_strategy,
            kb.chunk_size,
            kb.chunk_overlap,
            source={"kb_id": kb.id, "doc_id": doc.id},
        )
        if not chunks:
            raise ValueError("文档解析后无可分块内容")

        doc.status = "embedding"; doc.stage = "embed"; doc.progress = 70; db.commit()
        n = store.upsert_document(doc.id, kb.id, chunks)

        doc.status = "ready"; doc.stage = "done"; doc.progress = 100
        doc.chunk_count = n
        doc.error = None
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        doc.status = "failed"
        doc.error = str(e)
        db.commit()
```

- [ ] **Step 6: 写 api/documents.py**

创建 `backend/app/api/documents.py`:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Document, User
from app.schemas.document import DocumentOut
from app.services import document_service, ingestion_service

router = APIRouter(tags=["documents"])


@router.post(
    "/knowledge_bases/{kb_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    kb_id: int,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    kb = document_service.get_owned_kb(db, current_user, kb_id)
    file_type = (file.filename or "file").rsplit(".", 1)[-1].lower()
    raw = file.file.read()
    doc = Document(kb_id=kb.id, name=file.filename or "untitled", file_type=file_type, size=len(raw), status="uploading")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    background.add_task(ingestion_service.ingest_document, db, doc, raw)
    return doc


@router.get("/knowledge_bases/{kb_id}/documents", response_model=list[DocumentOut])
def list_docs(
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Document]:
    return document_service.list_documents(db, current_user, kb_id)


@router.get("/documents/{doc_id}", response_model=DocumentOut)
def get_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    return document_service.get_document(db, current_user, doc_id)


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    doc = document_service.delete_document(db, current_user, doc_id)
    get_qdrant_store().delete_document_chunks(doc.id)
```

> `get_qdrant_store()` 在 api 层需 import:`from app.rag.client import get_qdrant` 与 `from app.rag.embeddings import SiliconFlowEmbeddingProvider`、`from app.rag.vector_store import QdrantVectorStore`,并定义同 `ingestion_service._make_vector_store` 的工厂(简单起见 api 层也建一个,或直接复用 `ingestion_service._make_vector_store`)。

- [ ] **Step 7: main.py 挂载 documents 路由**

编辑 `backend/app/main.py`,import 并挂载:

```python
from app.api.documents import router as documents_router
# create_app 内:
    app.include_router(documents_router, prefix=settings.API_V1_PREFIX)
```

- [ ] **Step 8: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_documents.py -v
```

期望:3 passed。

- [ ] **Step 9: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/schemas/document.py backend/app/services/document_service.py backend/app/services/ingestion_service.py backend/app/api/documents.py backend/app/main.py backend/tests/test_documents.py
git commit -m "feat: add document upload API with background ingestion"
```

---

### Task 7: D3 收尾 —— 全量验证 + 提交

**Files:**
- 无新增(验证与收尾)

- [ ] **Step 1: 全量测试**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest -v
```

期望:全部 PASS(D1 5 + D2 11 + D3 约 14)。

- [ ] **Step 2: 生产 collection 冒烟(可选,需 SILICONFLOW_API_KEY)**

若 `.env` 已填 `SILICONFLOW_API_KEY`,手动冒烟一次真实链路:

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
python -c "
from app.rag.embeddings import SiliconFlowEmbeddingProvider
p = SiliconFlowEmbeddingProvider()
v = p.embed_texts(['你好世界'])
print('dims:', len(v[0]))
assert len(v[0]) == 1024
print('OK')
"
```

期望:打印 `dims: 1024` 与 `OK`。若报 401/缺 key,跳过并在 README 记录「真实嵌入需配置密钥」。

- [ ] **Step 3: 检查工作区**

```bash
cd /home/sjx_0/project/shixi
git status
git log --oneline -8
```

期望:工作区干净;log 显示 D3 的 6 个 commit。

- [ ] **Step 4: 收尾提交(若有遗漏)**

```bash
cd /home/sjx_0/project/shixi
git add -A
git commit -m "chore: complete D3 rag ingestion milestone" || echo "无待提交改动"
```
