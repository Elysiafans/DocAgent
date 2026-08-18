# DocAgent D6 —— 协议集成:MCP / Agent Skills / A2A / A2UI / 长期记忆 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 DocAgent 成为"懂 Agent 生态协议"的作品:自研 **MCP 服务端**(JSON-RPC 2.0 + streamable HTTP)、**Agent Skills**(SKILL.md 目录 + 加载工具)、**A2A 服务端**(JSON-RPC 2.0:agent/get、message/send、tasks/get)、**A2UI 卡片渲染**(结构化 UI 卡片)、**长期记忆**(Postgres 持久化 + agent 提示注入)。**零新增依赖**——MCP/A2A 官方 SDK 存在,但本里程碑手写协议实现以展示对协议本质的理解(JSON-RPC 2.0 信封、握手、方法表),同时规避与 fastapi 0.139 的兼容风险。

**Architecture:** 全部落在 D1 预留的 `backend/app/protocols/` 包内。每个协议 = 核心类(纯函数、可单测)+ API 层(鉴权 + 传输)。MCP/A2A 均挂在应用工厂(带 `/mcp`、`/a2a` 协议入口,A2UI/Skills/Memories 挂 `/api/v1`)。长期记忆复用 D5 的 agent 编排:记忆注入到 Supervisor 与 agent 的 SystemPrompt。

**Tech Stack:** 无新依赖。Python 标准库 `json`/`re`/`pathlib` + FastAPI/SQLAlchemy 现有栈。

## Global Constraints

- 本计划所有命令在 **WSL(Ubuntu-22.04)** 内执行。仓库路径 `/home/sjx_0/project/shixi`。
- Python 环境:**conda env `yy`**。所有 python/pytest/alembic 命令带前缀:`source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy && <cmd>`。**不要新建环境、不降级已有包、不新增依赖。**
- `.env`(含密钥)永不提交;只提交 `.env.example`;密钥填 `.env`。
- 测试只依赖本机/本地基础设施,**绝不调用真实 SiliconFlow/DeepSeek API**(注入 fake);测试 DB 恒为 `docagent_test`,不污染 dev DB。
- 真实冒烟用 `.env` 真实 key,结束后**完整清理**(用户/KB/文档/会话/消息/task_runs/memories + QDrant chunk 删除)。
- 提交信息用 conventional commits(`feat:` / `fix:` / `docs:` / `chore:` / `test:`)。
- 命令从 Windows 侧执行:git 用 UNC 路径 `//wsl.localhost/Ubuntu-22.04/home/sjx_0/project/shixi`,python/pytest 用 `wsl -d Ubuntu-22.04 -- bash -lc '...'`。

## 协议设计要点(先读再动手)

**MCP(streamable HTTP):**
- 请求/响应为 JSON-RPC 2.0 信封 `{"jsonrpc":"2.0","id":...,"method":...,"params":{...}}`。
- 实现方法:`initialize`(协议版本协商,回 `protocolVersion` + `capabilities.tools.listChanged=false` + `serverInfo`)、`notifications/initialized`(空结果)、`tools/list`(返回 4 个工具,含 `inputSchema`)、`tools/call`(执行并返回 `{"content":[{"type":"text","text":...}]}`)。
- `tools/call` 的 KB 工具 `knowledge_search`/`compare_documents` 带必选 `kb_id` 参数(鉴权归属校验),`calculator`/`web_search` 无 KB。
- 传输:`Accept: application/json` → 普通 JSON 响应;`Accept: text/event-stream` → SSE 帧 `event: message\ndata: <json>\n\n` + 终止帧 `{"jsonrpc":"2.0","result":{"_meta":{}},"id":null}`。
- 错误:JSON-RPC 标准码(-32700 解析 / -32600 无效请求 / -32601 方法不存在 / -32602 参数无效 / -32000 服务器内部)。

**Agent Skills:** 目录 `backend/skills/<name>/SKILL.md`,frontmatter 含 `name`/`description`。`skills.list_skills()` 扫描目录,`load_skill(name)` 读内容。`load_skill` 作为第 5 个 agent 工具注入(utility 可用)。

**A2A(JSON-RPC 2.0):** 方法 `agent/get`(返回 AgentCard,含 `skills` 列表与 capabilities)、`message/send`(params: message.parts[].text + metadata.kb_id → 复用 `agent_service.ask` 跑 Supervisor 图,返回 taskId+agent 文本消息)、`tasks/get`(按 run_id 查 TaskRun 返回状态与 artifact)。

**A2UI:** 卡片 JSON:顶层 `{cardId, type, header{title, subtitle}, parts[{kind:"text",text}], children[{type:"sources", sources:[...]}]}`。`render_message_card(msg, sources)` 把一条 assistant 消息渲染为卡片;`POST /a2ui/render` 即时渲染提问,`GET /a2ui/cards/{message_id}` 渲染已存消息。

**长期记忆:** 表 `memories(id, user_id FK, conv_id FK?, kind, content, meta JSONB, created_at)`。`memory_service` 提供 add/list/search/delete。`build_memory_context(db,user,limit=10)` 拼成文本块;`agent_service.prepare_agent_chat` 计算并放入 `PreparedRun.memory_context`;`build_graph(llm, tools, memory_context="")` 把该块追加到 Supervisor 与每个 agent 的 SystemPrompt。

---

### Task 1: MCP 服务端(自研)

**Files:**
- Create: `backend/app/protocols/jsonrpc.py`
- Create: `backend/app/protocols/mcp_server.py`
- Create: `backend/app/protocols/mcp_tools.py`
- Create: `backend/app/api/mcp.py`
- Modify: `backend/app/main.py`(mount `/mcp`)
- Test: `backend/tests/test_mcp.py`

**Interfaces:**
- `jsonrpc.success(id, result) -> dict` / `jsonrpc.error(id, code, message, data=None) -> dict`
- `jsonrpc.parse_request(data) -> tuple[method, id, params]`(raise JsonRpcError)
- `McpServer(tools: list[dict])`:tools 元素 `{"name","description","inputSchema","needs_kb":bool,"call": Callable[[ctx, arguments], str]}`
  - `handle(req: dict) -> dict`(返回 jsonrpc 信封;`tools/call` 时按需用 `ctx_factory(kb_id)` 重建上下文)
- `mcp_tools.ctx_factory`(由 API 层注入,鉴权归属校验)
- `McpServer.handle_batch(req: dict|list) -> dict|list`(支持批量)

- [ ] **Step 1: 写测试 `backend/tests/test_mcp.py`(先失败)**

覆盖:
1. `test_initialize_handshake` — `initialize` 回 protocolVersion(2025-03-26)+ serverInfo + capabilities
2. `test_tools_list` — 4 个工具,`knowledge_search` schema 含必选 `kb_id`
3. `test_tools_call_knowledge_search` — fake store + fake ctx_factory,`tools/call` 返回含文本的 content
4. `test_tools_call_unknown_method_error` — method 不存在 → code -32601
5. `test_parse_error` — 非法 JSON/缺 method → -32600/-32700
6. `test_mcp_http_json_mode` — `POST /mcp`(Accept: application/json)带 Bearer → JSON 响应
7. `test_mcp_http_sse_mode` — `client.stream("POST", "/mcp", Accept: text/event-stream)` 解析 `event: message` 帧
8. `test_mcp_requires_auth` — 无 token → 401

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现 `jsonrpc.py`、`mcp_server.py`、`mcp_tools.py`、`api/mcp.py`,mount `/mcp`**
- [ ] **Step 4: 运行确认全绿,`feat: add hand-rolled MCP server (tools/list + tools/call)`**

### Task 2: Agent Skills

**Files:**
- Create: `backend/skills/rag_qa/SKILL.md`
- Create: `backend/skills/web_research/SKILL.md`
- Create: `backend/app/protocols/skills.py`
- Create: `backend/app/api/skills.py`
- Modify: `backend/app/agents/tools.py`(追加 `load_skill` 工具)
- Modify: `backend/app/main.py`(mount `/api/v1/skills`)
- Test: `backend/tests/test_skills.py`

**Interfaces:**
- `skills.SKILLS_DIR`(=`backend/skills/`)
- `skills.list_skills() -> list[{"name","description"}]`
- `skills.load_skill(name) -> str`(KeyError 若不存在)
- `GET /api/v1/skills` → 技能列表

- [ ] **Step 1: 写测试(先失败)**:list 找到 rag_qa/web_research;load_skill 返回含 `knowledge_search` 的内容;未知技能 KeyError;`load_skill` 工具可被 scripted agent 调用(经 build_tools)
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现 skills.py + SKILL.md + 工具 + API**
- [ ] **Step 4: 运行确认全绿,`feat: add agent skills registry with load_skill tool`**

### Task 3: A2A 服务端 + 同步 ask

**Files:**
- Create: `backend/app/protocols/a2a.py`
- Create: `backend/app/api/a2a.py`
- Modify: `backend/app/services/agent_service.py`(`ask()` + `PreparedRun.memory_context`)
- Modify: `backend/app/main.py`(mount `/a2a`)
- Test: `backend/tests/test_a2a.py`

**Interfaces:**
- `agent_service.ask(db, user, payload) -> AskResult(answer, conversation_id, run_id, sources)`(复用 `prepare_agent_chat` + `stream_agent_chat`,排干事件流)
- `A2aServer.handle(req) -> dict`:`agent/get`、`message/send`、`tasks/get`;未知方法 -32601
- `message/send` params:`{"message":{"parts":[{"kind":"text","text":...}]},"metadata":{"kb_id":...}}`

- [ ] **Step 1: 写测试(先失败)**:agent/get 回 AgentCard(name/skills);message/send 回 taskId+agent 文本(scripted LLM + fake store);tasks/get 回 status=completed;未知方法 -32601;`POST /a2a` HTTP 带鉴权
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现 agent_service.ask + a2a.py + api/a2a.py**
- [ ] **Step 4: 运行确认全绿,`feat: add A2A JSON-RPC server (agent/get, message/send, tasks/get)`**

### Task 4: A2UI 卡片渲染

**Files:**
- Create: `backend/app/protocols/a2ui.py`
- Create: `backend/app/api/a2ui.py`
- Modify: `backend/app/main.py`(mount `/api/v1/a2ui`)
- Test: `backend/tests/test_a2ui.py`

**Interfaces:**
- `a2ui.render_message_card(message, sources) -> dict`(A2UI 卡片 JSON:cardId/type/header/parts/children)
- `POST /api/v1/a2ui/render`(body: kb_id+question+route? → `ask` 非流式渲染当前回答)
- `GET /api/v1/a2ui/cards/{message_id}`(渲染已存 assistant 消息)

- [ ] **Step 1: 写测试(先失败)**:render 单测(header/parts/children.sources);GET cards/{message_id} 渲染已存消息(先走 chat 造消息);render 端点鉴权
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现 a2ui.py + api/a2ui.py**
- [ ] **Step 4: 运行确认全绿,`feat: add A2UI card rendering endpoints`**

### Task 5: 长期记忆

**Files:**
- Create: `backend/app/models/memory.py` + 注册 `models/__init__.py`
- Create: Alembic migration(`add memories table`,autogenerate)
- Create: `backend/app/services/memory_service.py`
- Create: `backend/app/api/memories.py`
- Modify: `backend/app/agents/graph.py`(`build_graph(..., memory_context="")` 注入提示)
- Modify: `backend/app/services/agent_service.py`(prepare 计算 memory_context)
- Modify: `backend/app/main.py`(mount `/api/v1/memories`)
- Modify: `backend/tests/fake_model.py`(记录 `last_input`,供注入断言)
- Test: `backend/tests/test_memories.py`

**Interfaces:**
- `Memory(id, user_id FK, conv_id FK?, kind, content, meta, created_at)`
- `memory_service.add_memory / list_memories / search_memories / delete_memory`
- `memory_service.build_memory_context(db, user, limit=10) -> str`
- `GET/POST /api/v1/memories`、`DELETE /api/v1/memories/{id}`
- `build_graph(..., memory_context="")`;Supervisor 与 agent 的 SystemPrompt 追加记忆块

- [ ] **Step 1: 建表迁移 + 模型 + 注册**,`alembic upgrade head`
- [ ] **Step 2: 写测试(先失败)**:CRUD 全流程;search 关键字;delete 404 越权;`build_memory_context` 拼接;记忆注入——加记忆后 `agent_service.ask`(scripted LLM)断言 `llm.last_input[0]` 含记忆内容;agent 图(带 memory_context)supervisor 输入含记忆块
- [ ] **Step 3: 运行确认失败**
- [ ] **Step 4: 实现 memory_service + api + graph/agent 注入 + fake_model 记录**
- [ ] **Step 5: 运行确认全绿,`feat: add persistent long-term memory with agent prompt injection`**

### Task 6: D6 收尾

- [ ] **Step 1: 全量测试**(`pytest -q`,期望 D1-D5 64 + D6 新增 ~25 全绿)
- [ ] **Step 2: 真实冒烟 `tmp_d6_smoke.py`**(用后即删):真 LLM 下 —— MCP `tools/list`+`tools/call`(knowledge_search,真实 KB)、A2A `message/send` 全链路、A2UI `render` 出卡片、写入记忆后再次 ask 验证注入;完成后清理(用户/KB/文档/会话/消息/task_runs/memories + QDrant)
- [ ] **Step 3: 检查工作区**(`git status` 干净、log 显示 D6 6 个 commit)
- [ ] **Step 4: 收尾提交(若有遗漏)**
