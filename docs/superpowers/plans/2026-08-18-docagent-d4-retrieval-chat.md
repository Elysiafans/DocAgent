# DocAgent D4 —— RAG 检索 + 非流式 /chat 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通「查询 → 嵌入 → QDrant 混合检索(稠密+稀疏)→ RRF 融合 → bge-reranker 重排 → 上下文组装 → DeepSeek(deepseek-v4-flash)回答 + 溯源引用」的完整检索链路,并上线非流式 `POST /api/v1/chat`。

**Architecture:**
- `vector_store.search()`:QDrant **原生 prefetch + Fusion.RRF**,稠密(`dense`,bge-m3)+ 稀疏(`sparse`,BM25)同一 collection,`kb_id` payload 过滤。
- 新增 `app/rag/sparse.py`:**稳定 token→index 映射**(`zlib.crc32`,修掉 D3 用 `hash()` 导致的跨进程随机问题——否则检索永远匹配不上已存稀疏向量)。D3 的 `vector_store.upsert` 改用它,保持写入/查询一致。
- 新增 `app/rag/reranker.py`:`SiliconFlowReranker`(bge-reranker-v2-m3)+ `fake_rerank`(测试)。
- 新增 `app/rag/retrieval.py`:纯函数 `retrieve()`(重排/截断/阈值过滤)+ `assemble_context()`(编号段落)。
- 新增 `app/services/chat_service.py` + `app/api/chat.py`:非流式 `/chat`,保存会话与消息(Converation/Message 表),多轮自动带历史。附会话查询 API。
- 对话模型 **`deepseek-v4-flash`**(D3 已配好)。

**Tech Stack:** 无新增依赖(qdrant-client/langchain/openai 已装)。

## Global Constraints

- 沿用 D1-D3 约束:WSL、`yy` 环境、命令前缀 `source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy && <cmd>`。
- 容器需运行:`docker compose up -d`(postgres + qdrant)。
- **测试不触网**:嵌入/重排/对话 Provider 全部注入 fake;QDrant 用测试专用 collection `docagent_test_collection`;DB 用 `docagent_test`。
- 生产链路用 `.env` 的真实 key 做**收尾冒烟**(DEEPSEEK_API_KEY / SILICONFLOW_API_KEY 均已配置)。
- 密钥永不入库;提交用 conventional commits。
- 检索参数 API 化(设计规格 §4):`top_k`、`top_n`、`hybrid`、`threshold`,演示可现场改。

---

### Task 1: 稀疏向量稳定化 + 向量检索(search,原生 RRF)

**Files:**
- Create: `backend/app/rag/sparse.py`
- Modify: `backend/app/rag/vector_store.py`(upsert 改用 sparse.py;新增 `search()`、`SearchHit`)
- Create: `backend/tests/test_sparse.py`
- Modify: `backend/tests/test_vector_store.py`(补 search 测试)
- Test: `backend/tests/test_sparse.py`、`backend/tests/test_vector_store.py`

**Interfaces:**
- `app.rag.sparse.build_sparse_vector(text) -> tuple[list[int], list[float]]`(indices 升序去重,稳定 crc32)
- `QdrantVectorStore.search(query_text, kb_id, top_k=20, hybrid=True) -> list[SearchHit]`
- `SearchHit(doc_id, chunk_index, content, score, meta)`

- [ ] **Step 1: 写稀疏向量测试(先失败)**

创建 `backend/tests/test_sparse.py`:

```python
from app.rag.sparse import build_sparse_vector


def test_sparse_deterministic_across_calls():
    a1, v1 = build_sparse_vector("多智能体知识库 平台")
    a2, v2 = build_sparse_vector("多智能体知识库 平台")
    assert a1 == a2 and v1 == v2  # 稳定,跨进程一致


def test_sparse_indices_sorted_and_unique():
    indices, values = build_sparse_vector("A A B C C C")
    assert indices == sorted(indices)
    assert len(indices) == len(set(indices))
    assert sum(values) == 6  # A×2 + B×1 + C×3


def test_sparse_different_text_differs():
    i1, _ = build_sparse_vector("苹果")
    i2, _ = build_sparse_vector("香蕉")
    assert i1 != i2
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_sparse.py -v
```

期望:FAIL(`ModuleNotFoundError`)。

- [ ] **Step 3: 实现 sparse.py**

创建 `backend/app/rag/sparse.py`:

```python
import re
import zlib

_CJK_RE = re.compile(r"[一-鿿]")
_SEP_RE = re.compile(r"[\s。，,；;！？!?、()（）【】\[\]\"'：:]")


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
    """token -> 稳定 index(zlib.crc32,避免 hash() 跨进程随机)。indices 升序去重。"""
    counts: dict[int, float] = {}
    for tok in tokenize(text):
        idx = zlib.crc32(tok.encode("utf-8"))
        counts[idx] = counts.get(idx, 0) + 1.0
    indices = sorted(counts)
    return indices, [counts[i] for i in indices]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_sparse.py -v
```

期望:3 passed。

- [ ] **Step 5: 重构 vector_store(upsert 用 sparse.py + 新增 search)**

编辑 `backend/app/rag/vector_store.py`:

- import:`from app.rag.sparse import build_sparse_vector`
- `upsert_document` 的稀疏向量改用 `build_sparse_vector(c.content)`(替换 D3 内联 `hash()` 逻辑,保证与查询一致):

```python
            indices, values = build_sparse_vector(c.content)
            ...
                    vector={
                        "dense": vec,
                        "sparse": models.SparseVector(indices=indices, values=values),
                    },
```

- 新增 `SearchHit` dataclass 与 `search()`:

```python
from dataclasses import dataclass


@dataclass
class SearchHit:
    doc_id: int
    chunk_index: int
    content: str
    score: float
    meta: dict


    def search(
        self, query_text: str, kb_id: int, top_k: int = 20, hybrid: bool = True
    ) -> list[SearchHit]:
        """混合检索:稠密(dense)+ 稀疏(sparse)prefetch,原生 RRF 融合,按 kb_id 过滤。"""
        self.ensure_collection()
        dense = self.embedder([query_text])[0]
        kb_filter = models.Filter(
            must=[
                models.FieldCondition(key="kb_id", match=models.MatchValue(value=kb_id))
            ]
        )
        if hybrid:
            s_idx, s_vals = build_sparse_vector(query_text)
            prefetch = [
                models.Prefetch(query=dense, using="dense", limit=top_k, filter=kb_filter)
            ]
            if s_idx:
                prefetch.append(
                    models.Prefetch(
                        query=models.SparseVector(indices=s_idx, values=s_vals),
                        using="sparse",
                        limit=top_k,
                        filter=kb_filter,
                    )
                )
            resp = self._client.query_points(
                collection_name=self.collection,
                prefetch=prefetch,
                query=models.Fusion.RRF,
                limit=top_k,
                with_payload=True,
            )
        else:
            resp = self._client.query_points(
                collection_name=self.collection,
                query=dense,
                using="dense",
                query_filter=kb_filter,
                limit=top_k,
                with_payload=True,
            )
        hits = []
        for p in resp.points:
            pl = p.payload or {}
            hits.append(
                SearchHit(
                    doc_id=pl["doc_id"],
                    chunk_index=pl["chunk_index"],
                    content=pl["content"],
                    score=float(p.score),
                    meta=pl,
                )
            )
        return hits
```

> 注意:`prefetch` 为空(查询无 token)时退化为纯稠密;`hybrid=False` 走纯稠密。

- [ ] **Step 6: 补 search 测试**

在 `backend/tests/test_vector_store.py` 追加:

```python
def test_search_finds_relevant_chunk():
    store = _make_store()
    store.upsert_document(42, 1, _chunks())
    hits = store.search("chunk 1", 1, top_k=5)
    assert hits and hits[0].doc_id == 42
    assert hits[0].content == "chunk 1"
    # kb_id 过滤:别的库查不到
    assert store.search("chunk 1", 999, top_k=5) == []


def test_search_hybrid_and_dense_agree_on_top():
    store = _make_store()
    store.upsert_document(42, 1, _chunks())
    hybrid = store.search("chunk 1", 1, top_k=5, hybrid=True)
    dense = store.search("chunk 1", 1, top_k=5, hybrid=False)
    assert hybrid and dense
    assert hybrid[0].content == "chunk 1" == dense[0].content
```

- [ ] **Step 7: 运行相关测试**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_sparse.py tests/test_vector_store.py -v
```

期望:6 passed。

- [ ] **Step 8: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/rag/sparse.py backend/app/rag/vector_store.py backend/tests/test_sparse.py backend/tests/test_vector_store.py
git commit -m "feat: add stable sparse vectors and hybrid RRF search"
```

---

### Task 2: 重排器(bge-reranker-v2-m3)

**Files:**
- Create: `backend/app/rag/reranker.py`
- Test: `backend/tests/test_reranker.py`

**Interfaces:**
- `class Reranker(Protocol): rerank(query, documents, top_n) -> list[tuple[int, float]]`
- `SiliconFlowReranker`:POST `{base}/rerank`,按 relevance_score 降序取 top_n
- `fake_rerank(query, documents, top_n)`:按字符重叠度伪打分(测试)

- [ ] **Step 1: 写重排测试(先失败)**

创建 `backend/tests/test_reranker.py`:

```python
from app.rag.reranker import SiliconFlowReranker, fake_rerank


def test_fake_rerank_orders_by_overlap():
    docs = ["完全不相关的文字 abc", "苹果香蕉", "苹果"]
    ranked = fake_rerank("苹果", docs, top_n=2)
    assert len(ranked) == 2
    # 与"苹果"重叠最多的是 "苹果",其次 "苹果香蕉"
    assert ranked[0][0] == 2
    assert ranked[1][0] == 1
    assert ranked[0][1] >= ranked[1][1]


def test_siliconflow_rerank(monkeypatch):
    provider = SiliconFlowReranker()
    calls = []

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            payload = calls[-1]
            assert payload["model"] == "BAAI/bge-reranker-v2-m3"
            assert payload["query"] == "苹果"
            # 返回乱序,验证 provider 会按分数排序
            return {"results": [
                {"index": 0, "relevance_score": 0.1},
                {"index": 1, "relevance_score": 0.9},
                {"index": 2, "relevance_score": 0.5},
            ]}

    def fake_post(self, *args, **kwargs):
        calls.append(kwargs["json"])
        return FakeResp()

    monkeypatch.setattr("app.rag.reranker.httpx.Client.post", fake_post)
    ranked = provider.rerank("苹果", ["a", "b", "c"], top_n=2)
    assert ranked == [(1, 0.9), (2, 0.5)]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_reranker.py -v
```

期望:FAIL。

- [ ] **Step 3: 实现 reranker.py**

创建 `backend/app/rag/reranker.py`:

```python
from typing import Protocol

import httpx

from app.core.config import get_settings


class Reranker(Protocol):
    """重排抽象:输入 query + 候选文档,返回按相关度降序的 (index, score) 列表(取 top_n)。"""

    def rerank(
        self, query: str, documents: list[str], top_n: int
    ) -> list[tuple[int, float]]: ...


def fake_rerank(
    query: str, documents: list[str], top_n: int
) -> list[tuple[int, float]]:
    """伪重排:按 query 字符在文档中出现次数打分(测试用,确定性)。"""

    def score(doc: str) -> float:
        return float(sum(1 for ch in query if ch in doc))

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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_reranker.py -v
```

期望:2 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/rag/reranker.py backend/tests/test_reranker.py
git commit -m "feat: add reranker provider (bge-reranker-v2-m3)"
```

---

### Task 3: 检索服务(retrieve + 上下文组装)

**Files:**
- Create: `backend/app/rag/retrieval.py`
- Test: `backend/tests/test_retrieval.py`

**Interfaces:**
- `@dataclass RetrievedChunk: doc_id, chunk_index, content, score, meta, doc_name=None`
- `retrieve(store, reranker, query, kb_id, top_k=20, top_n=5, hybrid=True, threshold=None) -> list[RetrievedChunk]`
- `assemble_context(chunks, doc_names: dict[int, str]) -> str`(编号段落,供 prompt)

- [ ] **Step 1: 写检索测试(先失败)**

创建 `backend/tests/test_retrieval.py`:

```python
from app.rag.embeddings import fake_embed_texts
from app.rag.reranker import fake_rerank
from app.rag.retrieval import assemble_context, retrieve
from app.rag.vector_store import QdrantVectorStore

TEST_COLLECTION = "docagent_test_collection"


def _store():
    from app.rag.client import get_qdrant

    client = get_qdrant()
    if client.collection_exists(TEST_COLLECTION):
        client.delete_collection(TEST_COLLECTION)
    store = QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=8)
    store.ensure_collection()
    store.upsert_document(
        42, 1, _chunks_rich()
    )
    return store


def _chunks_rich():
    from app.rag.chunking import ChunkRecord

    return [
        ChunkRecord(index=i, content=t, char_count=len(t), hash=f"h{i}",
                    meta={"kb_id": 1, "doc_id": 42, "chunk_index": i})
        for i, t in enumerate(["苹果很好吃", "香蕉是黄色的", "西瓜很甜"])
    ]


def test_retrieve_reranks_and_truncates():
    store = _store()
    chunks = retrieve(store, fake_rerank, "苹果", 1, top_k=10, top_n=2)
    assert len(chunks) <= 2
    assert chunks[0].content == "苹果很好吃"
    assert chunks[0].score >= chunks[1].score


def test_retrieve_threshold_filters():
    store = _store()
    all_hits = retrieve(store, fake_rerank, "苹果", 1, top_k=10, top_n=5, threshold=0.0)
    # 全部保留(阈值 0)
    assert len(all_hits) >= 1
    # 高阈值 -> 可能为空
    strict = retrieve(store, fake_rerank, "苹果", 1, top_k=10, top_n=5, threshold=10.0)
    assert strict == []


def test_retrieve_empty_kb():
    store = _store()
    assert retrieve(store, fake_rerank, "苹果", 999, top_k=5) == []


def test_assemble_context_numbers_and_names():
    chunks = [
        type("C", (), {"doc_id": 1, "doc_name": "a.md", "chunk_index": 0, "content": "内容一"})(),
        type("C", (), {"doc_id": 2, "doc_name": "b.md", "chunk_index": 3, "content": "内容二"})(),
    ]
    ctx = assemble_context(chunks, {1: "a.md", 2: "b.md"})
    assert "[1]" in ctx and "a.md" in ctx
    assert "[2]" in ctx and "b.md" in ctx
```

> 说明:`threshold` 语义:重排后的 `score`(重排分数)低于阈值则丢弃。`fake_rerank` 分数=字符重叠数,"苹果" 对 "苹果很好吃" 得 2 分。

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_retrieval.py -v
```

期望:FAIL。

- [ ] **Step 3: 实现 retrieval.py**

创建 `backend/app/rag/retrieval.py`:

```python
from dataclasses import dataclass, field
from typing import Any

from app.rag.reranker import Reranker
from app.rag.vector_store import QdrantVectorStore


@dataclass
class RetrievedChunk:
    doc_id: int
    chunk_index: int
    content: str
    score: float
    meta: dict[str, Any] = field(default_factory=dict)
    doc_name: str | None = None


def retrieve(
    store: QdrantVectorStore,
    reranker: Reranker | None,
    query: str,
    kb_id: int,
    top_k: int = 20,
    top_n: int = 5,
    hybrid: bool = True,
    threshold: float | None = None,
) -> list[RetrievedChunk]:
    """检索流水线:search(混合+RRF)-> rerank(top_k->top_n)-> 阈值过滤。"""
    hits = store.search(query, kb_id, top_k=top_k, hybrid=hybrid)
    if not hits:
        return []
    if reranker is not None:
        ranked = reranker.rerank(query, [h.content for h in hits], top_n)
        chunks = [
            RetrievedChunk(
                doc_id=hits[i].doc_id,
                chunk_index=hits[i].chunk_index,
                content=hits[i].content,
                score=score,
                meta=hits[i].meta,
            )
            for i, score in ranked
        ]
    else:
        chunks = [
            RetrievedChunk(
                doc_id=h.doc_id,
                chunk_index=h.chunk_index,
                content=h.content,
                score=h.score,
                meta=h.meta,
            )
            for h in hits[:top_n]
        ]
    if threshold is not None:
        chunks = [c for c in chunks if c.score >= threshold]
    return chunks


def assemble_context(chunks: list[RetrievedChunk], doc_names: dict[int, str]) -> str:
    """把命中块编成带 [编号] 的上下文,供 prompt 使用并强制 LLM 按编号引用。"""
    lines = []
    for i, c in enumerate(chunks, 1):
        name = doc_names.get(c.doc_id, f"文档{c.doc_id}")
        lines.append(f"[{i}] {c.content} (来源:{name} 第{c.chunk_index + 1}块)")
    return "\n".join(lines)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_retrieval.py -v
```

期望:4 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/rag/retrieval.py backend/tests/test_retrieval.py
git commit -m "feat: add retrieval pipeline with rerank and context assembly"
```

---

### Task 4: DeepSeek 对话 Provider(deepseek-v4-flash)

**Files:**
- Create: `backend/app/rag/chat_provider.py`
- Test: `backend/tests/test_chat_provider.py`

**Interfaces:**
- `class ChatProvider(Protocol): complete(messages: list[dict[str, str]], temperature=0.2) -> str`
- `DeepSeekChatProvider`:openai 客户端,`base_url=DEEPSEEK_BASE_URL`、`model=DEEPSEEK_CHAT_MODEL`(= deepseek-v4-flash)

- [ ] **Step 1: 写对话 Provider 测试(先失败)**

创建 `backend/tests/test_chat_provider.py`:

```python
from app.rag.chat_provider import DeepSeekChatProvider


def test_deepseek_complete(monkeypatch):
    provider = DeepSeekChatProvider()
    calls = []

    class FakeChoices:
        def __init__(self, content):
            self.message = type("M", (), {"content": content})()

    class FakeResp:
        choices = [FakeChoices("根据资料[1],答案是……")]

    def fake_create(self, *args, **kwargs):
        calls.append(kwargs)
        return FakeResp()

    monkeypatch.setattr(
        "app.rag.chat_provider.OpenAI.chat.completions.create", fake_create
    )
    answer = provider.complete(
        [{"role": "user", "content": "hi"}], temperature=0.1
    )
    assert answer.startswith("根据资料")
    assert calls and calls[0]["model"] == "deepseek-v4-flash"
```

> 注意 monkeypatch 路径:`provider._client` 是 `openai.OpenAI` 实例,打桩它的 `chat.completions.create`。若 openai 客户端对象属性绑定方式不同,以实际对象结构调整。

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_chat_provider.py -v
```

期望:FAIL。

- [ ] **Step 3: 实现 chat_provider.py**

创建 `backend/app/rag/chat_provider.py`:

```python
from typing import Protocol

from openai import OpenAI

from app.core.config import get_settings


class ChatProvider(Protocol):
    def complete(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str: ...


class DeepSeekChatProvider:
    """DeepSeek 对话(deepseek-v4-flash),OpenAI 兼容接口。"""

    def __init__(self, temperature: float = 0.2):
        s = get_settings()
        self.model = s.DEEPSEEK_CHAT_MODEL
        self.temperature = temperature
        self._client = OpenAI(api_key=s.DEEPSEEK_API_KEY, base_url=s.DEEPSEEK_BASE_URL)

    def complete(self, messages: list[dict[str, str]], temperature: float | None = None) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature if temperature is not None else self.temperature,
        )
        return resp.choices[0].message.content or ""
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_chat_provider.py -v
```

期望:1 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/rag/chat_provider.py backend/tests/test_chat_provider.py
git commit -m "feat: add deepseek chat provider (v4-flash)"
```

---

### Task 5: /chat API + 会话/消息持久化 + 会话查询

**Files:**
- Create: `backend/app/schemas/chat.py`
- Create: `backend/app/schemas/conversation.py`
- Create: `backend/app/services/chat_service.py`
- Create: `backend/app/api/chat.py`
- Create: `backend/app/api/conversations.py`
- Modify: `backend/app/main.py`(挂载两个路由)
- Test: `backend/tests/test_chat.py`

**Interfaces:**
- `POST /api/v1/chat` → `ChatResponse{answer, sources, conversation_id}`
  - Request:`ChatRequest{kb_id, question, conversation_id?, top_k=20, top_n=5, hybrid=True, threshold?}`
- `GET /api/v1/conversations` → 当前用户会话列表
- `GET /api/v1/conversations/{conv_id}/messages` → 消息列表(含 sources)
- 流程:校验 KB 归属 → 检索(注入式 provider)→ 组装编号上下文 → 历史(多轮)→ DeepSeek → 存 user+assistant 消息 → 返回

- [ ] **Step 1: 写 /chat 测试(先失败)**

创建 `backend/tests/test_chat.py`:

```python
import app.services.chat_service as chat_svc
from app.rag.chat_provider import ChatProvider
from app.rag.embeddings import fake_embed_texts
from app.rag.reranker import fake_rerank
from app.rag.vector_store import QdrantVectorStore

TEST_COLLECTION = "docagent_test_collection"
DOC_BYTES = "DocAgent 是多智能体知识库问答平台,支持 RAG 检索。".encode()


class FakeChat(ChatProvider):
    def complete(self, messages, temperature=0.2):
        assert any(m["role"] == "system" for m in messages)
        return "答案是[1]:多智能体知识库。详见资料[1]。"


def _patch_providers(monkeypatch):
    monkeypatch.setattr(
        chat_svc, "_make_vector_store",
        lambda kb_id: QdrantVectorStore(TEST_COLLECTION, fake_embed_texts, dim=8),
    )
    monkeypatch.setattr(chat_svc, "_make_reranker", fake_rerank)
    monkeypatch.setattr(chat_svc, "_make_chat_provider", FakeChat)


def _setup(client):
    client.post("/api/v1/auth/register", json={"email": "c@test.com", "password": "password123"})
    tok = client.post("/api/v1/auth/login", json={"email": "c@test.com", "password": "password123"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    kb_id = client.post("/api/v1/knowledge_bases", json={"name": "聊天库"}, headers=h).json()["id"]
    client.post(f"/api/v1/knowledge_bases/{kb_id}/documents",
                files={"file": ("r.md", DOC_BYTES)}, headers=h)
    return h, kb_id


def test_chat_end_to_end(client, monkeypatch):
    _patch_providers(monkeypatch)
    h, kb_id = _setup(client)
    r = client.post("/api/v1/chat", json={"kb_id": kb_id, "question": "什么是多智能体?"}, headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["answer"] and "[1]" in data["answer"]
    assert len(data["sources"]) >= 1
    assert data["sources"][0]["doc_name"] == "r.md"
    conv_id = data["conversation_id"]

    # 多轮:复用 conversation_id,带历史
    r2 = client.post("/api/v1/chat", json={"kb_id": kb_id, "question": "RAG 是什么?", "conversation_id": conv_id}, headers=h)
    assert r2.status_code == 200

    # 会话与消息已持久化
    convs = client.get("/api/v1/conversations", headers=h).json()
    assert any(c["id"] == conv_id for c in convs)
    msgs = client.get(f"/api/v1/conversations/{conv_id}/messages", headers=h).json()
    assert len(msgs) == 4  # 两轮 × (user+assistant)
    assert msgs[1]["sources"] and msgs[1]["sources"][0]["doc_name"] == "r.md"


def test_chat_requires_owned_kb(client, monkeypatch):
    _patch_providers(monkeypatch)
    h, _ = _setup(client)
    r = client.post("/api/v1/chat", json={"kb_id": 999, "question": "hi"}, headers=h)
    assert r.status_code == 404


def test_chat_requires_auth(client):
    assert client.post("/api/v1/chat", json={"kb_id": 1, "question": "hi"}).status_code == 401
```

> 关键:chat_service 里三个工厂函数 `_make_vector_store` / `_make_reranker` / `_make_chat_provider` 被 monkeypatch。FakeChat 断言 system prompt 存在,验证提示词工程注入。

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_chat.py -v
```

期望:FAIL。

- [ ] **Step 3: 写 schemas**

创建 `backend/app/schemas/chat.py`:

```python
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    kb_id: int
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None
    top_k: int = Field(default=20, ge=5, le=100)
    top_n: int = Field(default=5, ge=1, le=20)
    hybrid: bool = True
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class ChatSource(BaseModel):
    doc_id: int
    doc_name: str | None
    chunk_index: int
    content: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    conversation_id: int
```

创建 `backend/app/schemas/conversation.py`:

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kb_id: int
    title: str
    created_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conv_id: int
    role: str
    content: str
    sources: dict[str, Any] | None
    created_at: datetime
```

- [ ] **Step 4: 写 chat_service.py**

创建 `backend/app/services/chat_service.py`:

```python
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Conversation, Document, Message, User
from app.rag.chat_provider import ChatProvider, DeepSeekChatProvider
from app.rag.embeddings import SiliconFlowEmbeddingProvider
from app.rag.reranker import Reranker, SiliconFlowReranker
from app.rag.retrieval import assemble_context, retrieve
from app.rag.vector_store import QdrantVectorStore
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource

SYSTEM_PROMPT = """你是一个严谨的知识库问答助手。
规则:
1. 只依据下方"资料"回答;资料中没有的信息,明确说明"资料中没有相关内容",不要编造。
2. 引用来源:回答中引用资料内容时,用 [数字] 标注,数字对应资料编号。
3. 默认用与用户提问相同的语言回答。"""


def _make_vector_store(kb_id: int) -> QdrantVectorStore:
    return QdrantVectorStore(get_settings().QDRANT_COLLECTION, SiliconFlowEmbeddingProvider())


def _make_reranker() -> Reranker:
    return SiliconFlowReranker()


def _make_chat_provider() -> ChatProvider:
    return DeepSeekChatProvider()


def _get_owned_kb(db: Session, user: User, kb_id: int):
    kb = db.get(__import__("app.models", fromlist=["KnowledgeBase"]).KnowledgeBase, kb_id)
    if kb is None or kb.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    return kb


def _get_owned_conversation(db: Session, user: User, conv_id: int) -> Conversation:
    conv = db.get(Conversation, conv_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv


def chat(db: Session, user: User, payload: ChatRequest) -> ChatResponse:
    kb = _get_owned_kb(db, user, payload.kb_id)
    store = _make_vector_store(kb.id)
    chunks = retrieve(
        store, _make_reranker(), payload.question, kb.id,
        top_k=payload.top_k, top_n=payload.top_n,
        hybrid=payload.hybrid, threshold=payload.threshold,
    )
    # 文档名映射(溯源)
    doc_names: dict[int, str] = {}
    if chunks:
        doc_ids = {c.doc_id for c in chunks}
        doc_names = {
            d.id: d.name for d in db.execute(
                select(Document).where(Document.id.in_(doc_ids))
            ).scalars()
        }
    context = assemble_context(chunks, doc_names)

    # 会话:新建或复用(多轮带历史)
    history: list[tuple[str, str]] = []
    if payload.conversation_id:
        conv = _get_owned_conversation(db, user, payload.conversation_id)
        if conv.kb_id != kb.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Conversation belongs to another knowledge base")
        history = [
            (m.role, m.content) for m in db.execute(
                select(Message).where(Message.conv_id == conv.id).order_by(Message.id)
            ).scalars()
        ]
    else:
        conv = Conversation(user_id=user.id, kb_id=kb.id, title=payload.question[:30])
        db.add(conv)
        db.commit()
        db.refresh(conv)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend({"role": role, "content": content} for role, content in history[-8:])
    user_content = f"资料:\n{context}\n\n问题: {payload.question}" if context else f"资料: (无)\n\n问题: {payload.question}"
    messages.append({"role": "user", "content": user_content})
    answer = _make_chat_provider().complete(messages)

    sources = [
        ChatSource(
            doc_id=c.doc_id, doc_name=doc_names.get(c.doc_id),
            chunk_index=c.chunk_index, content=c.content, score=round(c.score, 4),
        )
        for c in chunks
    ]
    db.add(Message(conv_id=conv.id, role="user", content=payload.question))
    db.add(Message(
        conv_id=conv.id, role="assistant", content=answer,
        sources=[s.model_dump() for s in sources] or None, agent_type="retrieval_qa",
    ))
    db.commit()
    return ChatResponse(answer=answer, sources=sources, conversation_id=conv.id)


def list_conversations(db: Session, user: User):
    return list(db.execute(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.id.desc())
    ).scalars())


def list_messages(db: Session, user: User, conv_id: int):
    _get_owned_conversation(db, user, conv_id)
    return list(db.execute(
        select(Message).where(Message.conv_id == conv_id).order_by(Message.id)
    ).scalars())
```

> 注:`_get_owned_kb` 也可改为直接 `from app.models import KnowledgeBase` 更清晰;执行时以最简洁写法为准。

- [ ] **Step 5: 写 api/chat.py 与 api/conversations.py**

创建 `backend/app/api/chat.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat_service

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    return chat_service.chat(db, current_user, payload)
```

创建 `backend/app/api/conversations.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.conversation import ConversationOut, MessageOut
from app.services import chat_service

router = APIRouter(tags=["conversations"])


@router.get("/conversations", response_model=list[ConversationOut])
def list_convs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return chat_service.list_conversations(db, current_user)


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
def list_msgs(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return chat_service.list_messages(db, current_user, conv_id)
```

- [ ] **Step 6: main.py 挂载路由**

编辑 `backend/app/main.py`,import 并挂载:

```python
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
# create_app 内:
    app.include_router(chat_router, prefix=settings.API_V1_PREFIX)
    app.include_router(conversations_router, prefix=settings.API_V1_PREFIX)
```

- [ ] **Step 7: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_chat.py -v
```

期望:3 passed。

- [ ] **Step 8: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/schemas/chat.py backend/app/schemas/conversation.py backend/app/services/chat_service.py backend/app/api/chat.py backend/app/api/conversations.py backend/app/main.py backend/tests/test_chat.py
git commit -m "feat: add non-streaming /chat with retrieval and citations"
```

---

### Task 6: D4 收尾 —— 全量验证 + 真实冒烟

**Files:**
- 无新增(验证与收尾)

- [ ] **Step 1: 全量测试**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest -v
```

期望:全部 PASS(D1 5 + D2 11 + D3 18 + D4 约 15)。

- [ ] **Step 2: 真实链路冒烟(用 .env 真实 key)**

在 WSL 写临时脚本 `backend/../tmp_d4_smoke.py`(结束后删除),做:

1. TestClient 注册/登录 → 建 KB → 上传一个真实 md 文件(走 D3 后台摄取,真嵌入)
2. `POST /api/v1/chat`(真 bge-m3 + 真 rerank + 真 deepseek-v4-flash)
3. 断言:回答非空、含 `[1]`、sources 非空、conversation_id 存在
4. 打印回答与 sources 摘要
5. 清理:删文档/KB/用户,清 QDrant

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
PYTHONPATH=/home/sjx_0/project/shixi/backend python ../tmp_d4_smoke.py
```

> 注意:用 POST 响应体拿到 doc 后需**重新 GET** 才能看到后台任务结果(D3 已踩过坑);chat 的 background 任务同步执行,响应即最终态。

- [ ] **Step 3: 检查工作区**

```bash
cd /home/sjx_0/project/shixi
git status
git log --oneline -8
```

期望:工作区干净;log 显示 D4 的 6 个 commit。

- [ ] **Step 4: 收尾提交(若有遗漏)**

```bash
cd /home/sjx_0/project/shixi
git add -A
git commit -m "chore: complete D4 rag retrieval milestone" || echo "无待提交改动"
```
