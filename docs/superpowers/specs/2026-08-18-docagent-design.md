# DocAgent —— 多智能体协同的知识库问答平台 设计文档

日期:2026-08-18
作者:sjx_0
状态:已批准(2026-08-18)

---

## 1. 产品定位

一个让用户上传自己的文档、然后通过**多个分工明确的智能体**进行问答和深度分析的知识库问答平台。以 **RAG 为底座**,以 **LangGraph 多智能体编排**为亮点。

用途:求职展示作品,用于 AI 应用开发工程师岗位。交付到 GitHub,README 是作品的一部分。

### 核心用户流程

1. 注册/登录(JWT)
2. 创建知识库
3. 上传文档(PDF / Word / Markdown / TXT)
4. 文档后台异步处理:解析 → 分块 → 嵌入 → 存入 QDrant(前端显示四阶段进度)
5. 进入会话提问 → 路由器智能体判断意图 → 分发给对应专职智能体
6. 专职智能体检索知识库 / 调工具 → 流式回答 + 溯源引用(点击跳原文)
7. 多轮追问(会话记忆)+ 长期问答沉淀(向量记忆)

### 四个专职智能体

| 智能体 | 职责 | 编排方式 |
|---|---|---|
| 检索问答员 | 默认;混合检索 + 重排 + 带引用回答 | ReactAgent |
| 总结分析员 | 跨文档/跨知识库概括提炼、摘要 | ReactAgent |
| 对比分析员 | 多文档对比(如两份合同、两个版本差异) | 子图:并行检索多文档 → 对比 → 汇总 |
| 代码解答员 | 从代码类文档解答问题,代码块高亮输出 | ReactAgent |

另有一个 **路由器智能体(Supervisor)**:用 LangGraph 状态机,第一轮判断意图并委派任务;需要时自己也能调检索工具。

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────┐
│  Vue 3 + Vite (Vue Router / Pinia / Element Plus)     │
│  登录页 · 知识库管理页 · 聊天页(流式)· 溯源面板 · 运行追踪 │
└───────────────┬─────────────────────────────────────┘
                │ REST API + SSE (流式)
┌───────────────▼─────────────────────────────────────┐
│  FastAPI 后端                                          │
│  ┌─────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │ API 层  │→ │ Service 层│→ │ 领域层(核心)           │ │
│  │ 路由/鉴权│  │ 业务用例  │  │  RAG 引擎 / Agent 编排 │ │
│  │ DTO/校验 │  │ 用户/文档 │  │  协议层(MCP/A2A)      │ │
│  └─────────┘  │ 会话      │  │  提示词模板库          │ │
│               └──────────┘  └──────────────────────┘ │
│        中间件:统一异常/响应 · 日志 · 限流 · CORS       │
└───────┬──────────────────┬───────────────────────────┘
        │ SQLAlchemy        │ QDrant 客户端
┌───────▼───────┐  ┌───────▼─────────────────────────┐
│ PostgreSQL     │  │ QDrant (Docker)                 │
│ 业务数据       │  │ 每个知识库一个 collection        │
└───────────────┘  └─────────────────────────────────┘
        ▲ 外部模型:DeepSeek(对话) · SiliconFlow(嵌入 bge-m3 / 重排 bge-reranker)
```

### 分层原则

- **API 层**:只做路由、参数校验、DTO 序列化,不承载业务。
- **Service 层**:业务用例(用户、知识库、文档、会话)。
- **领域层**:RAG 引擎、Agent 编排、协议层、提示词模板库 —— 独立于 FastAPI 请求上下文,便于单元测试。
- **Infrastructure 层**:PostgreSQL(SQLAlchemy)、QDrant 客户端、模型提供商客户端。
- **模型提供商抽象层**:`LLMProvider` / `EmbeddingProvider` / `RerankProvider` 三个接口;实现 `DeepSeekProvider`(对话)、`SiliconFlowProvider`(嵌入 + 重排),预留 `OllamaProvider`。通过 `.env` 切换 —— 展示"国内外主流大模型可切换配置"。
- **设计模式可讲点**:Repository(存储抽象)、Provider 工厂(模型提供商)、策略(分块策略、检索策略)、依赖注入、模板方法(提示词渲染)。

---

## 3. 数据模型

### PostgreSQL(SQLAlchemy 2 + Alembic 迁移)

| 表 | 关键字段 | 说明 |
|---|---|---|
| `users` | id, email, hashed_password, created_at | JWT 鉴权 |
| `knowledge_bases` | id, name, description, owner_id, chunk_size, chunk_overlap, chunk_strategy, created_at | 分块策略参数存知识库级 |
| `documents` | id, kb_id, name, file_type, size, status(uploading/processing/ready/failed), progress(0-100), stage(parse/chunk/embed/finish), chunk_count, error, created_at | 处理状态机;`stage`+`progress` 供前端四阶段进度条 |
| `doc_chunks` | id, doc_id, chunk_index, content, char_count, hash(幂等去重), metadata JSONB(页码/标题层级/偏移) | 分块元数据,向量在 QDrant |
| `conversations` | id, user_id, kb_id, title, created_at | 会话 |
| `messages` | id, conv_id, role, content, sources JSONB(溯源), agent_type, created_at | 消息含溯源 |
| `task_runs` | id, type, status, error, started_at, finished_at, trace JSONB | 文档处理 / agent 运行跟踪 |

### QDrant

- 每个知识库一个 collection(命名 `kb_{kb_id}`),payload 存 `doc_id`、`chunk_index`、`kb_id`。
- 每个点一个**稠密向量**(bge-m3, 1024 维)+ 一个**稀疏向量**(BM25)。
- 长期记忆单独 collection(`memory_{user_id}`),存历史问答对。

---

## 4. RAG 链路

```
文档上传 → 解析(pdf/word/md/txt)→ 分块 → 嵌入(bge-m3)→ 存 QDrant
                                              ↓ 提问
                        查询 → 嵌入 → QDrant 混合检索(稠密+稀疏)
                                              ↓
                              重排(bge-reranker-v2-m3)→ 组装上下文 → DeepSeek 回答
                                              ↓
                                    溯源引用 [1][2] → 前端点击跳原文
```

### 文档解析

- PDF:`pypdf` / `pdfplumber`(保留页码)
- Word:`python-docx`
- Markdown / TXT:直接读取
- 解析器按文件类型策略分发,接口统一,便于扩展。

### 分块策略(知识库级可配置,体现"常用分块策略")

- **默认:递归字符分块**,`separators` 按中文标点适配:优先级 `\n\n` → `\n` → `。` → `；` → `,` → 空格,避免英文默认分隔符把中文切碎。
- **增强:Markdown 标题感知分块**,用 `MarkdownHeaderTextSplitter` 保留标题层级结构,分块时把各级标题拼进 chunk 内容(提升召回上下文完整度)。
- 参数:`chunk_size`(默认 800)、`chunk_overlap`(默认 100)、`chunk_strategy`(recursive / markdown_header),通过 API 配置存知识库。
- 每块计算 `hash` 做幂等去重,重复上传同一文档不重复入库。

### 嵌入

- SiliconFlow `BAAI/bge-m3`,批量嵌入,带简单缓存与重试。
- 通过 `EmbeddingProvider` 抽象,可切换其他提供商。

### 检索(混合检索 + 重排,体现"检索策略")

1. 查询文本 → 嵌入得到稠密向量。
2. QDrant 原生**稀疏向量**(BM25 模型)做关键词检索 —— 与稠密检索在**同一 collection**。
3. **RRF(Reciprocal Rank Fusion)融合**两路结果,取 top-K(默认 20)。
4. **重排**:SiliconFlow `bge-reranker-v2-m3` 对 top-K 重排,取 top-N(默认 5)。
5. 分数归一化;可选分数阈值过滤。
6. 检索参数 API 化:`top_k`、`top_n`、是否混合检索、阈值 —— 演示时可现场改参数看效果。

### 溯源与上下文组装

- 每个命中 chunk 携带:`文档名 / 页码 / 标题路径 / 相似度 / 在原文中的偏移`。
- prompt 中给段落编号,强制 LLM 用 `[1][2]` 标注引用。
- 前端把 `[n]` 渲染成可点击标注 → 溯源面板显示对应原文。

---

## 5. 多智能体编排(LangGraph)

```
        用户提问
           │
     ┌─────▼─────┐
     │ 路由器     │  Supervisor:分类意图 + 决定是否调工具
     └──┬──┬──┬──┘
    ┌────┘  │  └────┐
    ▼       ▼       ▼
 检索问答员 总结分析员 对比分析员
 (ReactAgent) (ReactAgent) (子图:并行检索多文档→对比)
    │       │       │
    └─── 共享工具集 + 共享记忆 ───┘
           │
     ┌─────▼─────┐
     │ 回答 + 溯源 │
     └───────────┘
```

### 实现要点

- 专职智能体基于 `langgraph.prebuilt.create_react_agent`,ReAct 循环 + 工具。
- **工具集**:
  - `knowledge_search(query, top_k, filter)` —— 走 RAG 检索,核心工具
  - `web_search(query)` —— DuckDuckGo 免费版,展示工具调用
  - `calculator(expr)` —— 简单工具
  - 对比分析员的工具内部走**子图**:并行对多个文档/多路检索做分片检索再汇总。
- **状态**:`TypedDict`,含 `messages`、`current_kb`、`retrieved_sources`。
- **记忆机制**:
  - 短期记忆:会话内消息历史,由 LangGraph 状态 + 内存/Postgres checkpointer 管理,支持多轮追问与指代。
  - 长期记忆:历史高质量问答对嵌入存入 QDrant `memory_{user_id}` collection,提问时检索相关历史作为参考;前端有记忆开关。
- **可观测**:每次运行的节点调用链、工具调用、状态流转写入 `task_runs.trace`,前端"运行追踪"面板可视化。

---

## 6. 协议层与提示词工程

### MCP(双向)

- **MCP Server**:用官方 `mcp` Python SDK,把 `knowledge_search` / `summarize` 暴露为 MCP tools,提供 stdio + HTTP(StreamableHTTP)transport。演示:用 MCP client(如 Claude Code)直接调用知识库检索。
- **MCP Client**:Agent 通过 `langchain-mcp-adapters` 挂载外部 MCP Server 工具。

### Agent Skills

- 后端提供 `skills/` 目录,内置 2-3 个 Skill(如 `report-writing`、`code-explain`),每个含 `SKILL.md`(名称/描述/使用时机/步骤)。
- Agent 运行时可发现并加载 Skill;README 展示 SKILL.md 结构。

### A2A

- 实现 **AgentCard**(`/.well-known/agent.json`:能力、端点、认证方式)+ **Task/Message 端点**(`/a2a/tasks`,支持 `tasks/send`、轮询、流式)。
- 交付演示脚本:模拟第二个 Agent 发现 AgentCard → 创建 Task → 提交问题 → 拿结果。
- 用官方 `a2a-python` SDK 降低实现成本,核心逻辑手写展示理解。

### A2UI(轻量版)

- Agent 支持返回**结构化输出块**(`table` / `quote` / `steps` / `chart` 数据),前端有对应渲染器。
- 例如对比分析员输出对比表格 → 前端渲染成表格卡片。作为 A2UI 结构化组件协议的轻量演示。

### 提示词工程

- 所有系统提示词集中在 `prompt_templates/`(或 DB 表),模板 + 变量注入(知识库名、检索上下文、时间、会话历史)。
- 显式落地技巧:角色设定、few-shot 示例、指令优先级("只能基于上下文回答,找不到就直说")、输出格式约束(JSON schema、引用格式 `[1][2]`)。
- 提供 API 查看/调整各 agent 提示词,前端设置页可查看。

---

## 7. 前端(Vue 3)

- 技术栈:Vue 3 + Vite + Vue Router + Pinia + Element Plus + `markdown-it` + `highlight.js`,深色模式。
- 页面:
  1. **登录/注册页**
  2. **知识库管理页**:知识库卡片、文档列表、上传进度(四阶段)、分块策略参数设置
  3. **聊天页**:流式消息、`[n]` 溯源标注 → 溯源面板、侧边会话历史、**Agent 运行追踪面板**、记忆开关
  4. **设置页**:模型提供商配置、各 Agent 提示词模板查看
- 流式:后端 SSE(fetch + ReadableStream),逐 token 渲染;agent 节点状态通过单独 SSE 事件推送。
- 前端为纯展示 + 交互层,所有逻辑走后端 API。

---

## 8. 工程化

- **Docker Compose**:`frontend`(nginx)+ `backend`(uvicorn)+ `postgres` + `qdrant`,健康检查、数据卷、`.env` 注入、优雅停止。
- **配置**:`.env` 集中管理,提交 `.env.example`,keys 绝不入库。
- **日志**:结构化 JSON 日志,request id 贯穿。
- **测试**:
  - 单元:分块、检索重排、prompt 组装(外部 API 用 Mock)
  - API 集成:httpx + 真实 Postgres/QDrant(或内存替代)
  - 端到端:一条完整 RAG 问答链路
- **Git**:`git init` + 按功能拆分清晰提交(conventional commits)。
- **GitHub 交付物**:
  - README:项目介绍、Mermaid 架构图、**功能↔岗位要求对照表**、截图 + 演示 gif、快速开始、目录结构、未来计划
  - GitHub Actions CI:lint + test
  - (可选)GitHub Pages 静态说明页

---

## 9. 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.11+, FastAPI, SQLAlchemy 2 + Alembic, PostgreSQL 16 |
| RAG | LangChain(分块/文档加载器)、QDrant(稠密+稀疏混合检索、RRF)、bge-m3 嵌入、bge-reranker-v2-m3 重排(SiliconFlow)、BM25 稀疏检索 |
| Agent | LangGraph(`create_react_agent`、子图、checkpointer)、工具函数 |
| 协议 | `mcp` Python SDK、`langchain-mcp-adapters`、`a2a-python` |
| 前端 | Vue 3 + Vite + Pinia + Vue Router + Element Plus + markdown-it |
| 鉴权 | JWT + bcrypt |
| 工程 | Docker Compose(nginx/uvicorn/postgres/qdrant)、GitHub Actions、pytest |

依赖全部锁版本;LangGraph/LangChain 用稳定版本,不用最新 beta。

---

## 10. 实现里程碑

| 天 | 交付点 |
|---|---|
| D1 | 仓库骨架:git init、monorepo 结构、后端分层骨架、.env/.env.example、日志中间件、Alembic 初始化、Postgres 起跑 |
| D2 | 数据模型 + 鉴权:全部表、JWT 注册登录、知识库 CRUD API |
| D3 | 文档处理 + RAG 底座:解析器、分块策略(可配置)、嵌入、QDrant 写入、上传 API + 后台进度 |
| D4 | RAG 检索:混合检索 + RRF + 重排 + 溯源 + 上下文组装,/chat 非流式打通 |
| D5 | Agent 编排:Supervisor 路由器 + 4 个专职 agent + 工具 + 会话记忆,SSE 流式 |
| D6 | 协议层:MCP Server/Client、A2A、Agent Skills、A2UI 结构化输出、长期向量记忆 |
| D7 | 前端:全部页面、流式聊天、溯源面板、运行追踪面板 |
| D8 | 测试(单测 + 集成 + E2E)+ Docker Compose 全链路 + 全量验证 |
| D9 | README(架构图/对照表/截图/gif)+ GitHub Actions CI + 上传 GitHub + 打磨 |

里程碑之间相互独立,可随时中断恢复。

---

## 11. 非目标(本作品刻意不做,YAGNI)

- 不做复杂用户角色权限(只有登录用户,无管理员/团队)
- 不做全文检索的 Elasticsearch 版(用 QDrant 稀疏向量承担关键词检索)
- 不做多租户、计费、审计
- 不做前端单元测试框架选型(以单测后端为主;前端保证构建通过 + 手测)
- 不本地微调模型、不做模型评测

---

## 12. 风险与开放问题

1. **SiliconFlow 账号**:需要用户注册硅基流动(免费额度覆盖 bge-m3 与 reranker)。若额度不足,备选:智谱 embedding-3/rerank(需另注册)或本地 Ollama(bge-m3,质量略降)。
2. **Docker Desktop 未启动**:运行时需先启动 Docker Desktop。
3. **前端 Vue3 经验**:若此前仅用过 FastAPI 模板渲染,需预留学习时间(D7 有缓冲,且框架脚手架可代劳大部分)。
4. **A2A 流式**:A2A 流式(send 返回 stream)若 SDK 支持有限,退化为任务轮询模式。
5. **DuckDuckGo 可用性**:若网络受限,`web_search` 工具可替换为国内可访问的搜索 API,或标记为可选工具。
6. **DeepSeek 高峰限流**:对话接口加超时与重试;`deepseek-reasoner` 作为可选模型,默认 `deepseek-chat`。
