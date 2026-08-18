# DocAgent D7 —— Vue 3 前端(SSE 对话 + 知识库 + 可观测) 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 用 Vue 3 + Vite 实现单页前端,直接对接后端全部能力:登录/注册、知识库管理(建库/上传文档/状态轮询/删除)、**SSE 流式 agent 对话**(实时 token、路由徽标、工具调用、溯源 sources)、A2UI 卡片渲染、task_runs 可观测。纯 fetch + 原生 CSS,不引 UI 框架/router/pinia/axios,保持依赖最小。

**Architecture:** `frontend/` Vite 单页应用(Composition API)。开发用 Vite dev server(代理 `/api`、`/mcp`、`/a2a` → `localhost:8000`);生产由 FastAPI StaticFiles 挂载 `frontend/dist`(D8 接入 Docker)。视图切换用 App.vue 响应式 `currentView`,不用 vue-router。

**Tech Stack:** Vue 3.5、Vite 6、@vitejs/plugin-vue 5。Node 环境:独立二进制 `~/tools/node-v20.20.2-linux-x64`(非 conda,不污染 `yy`)。

## Global Constraints

- 本计划所有命令在 **WSL(Ubuntu-22.04)** 内执行;前端命令需先设固定 PATH(避免 `$PATH` 引号展开坑):
  `export PATH=/home/sjx_0/tools/node-v20.20.2-linux-x64/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin && npm ...`
- 后端命令沿用 `source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy && <cmd>`(`yy` 环境)。
- `.env` 永不提交;`.gitignore` 增补 `frontend/node_modules/`、`frontend/dist/`。
- 测试只依赖本机基础设施;前端验证以 `npm run build` 成功 + dev/preview 可访问为准(无浏览器 E2E)。
- 提交信息用 conventional commits。
- 后端 API 已全部就绪(D1-D6),前端只消费,不回头改后端(除非发现接口 bug)。

---

### Task 1: 脚手架 + 布局

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/.gitignore`(node_modules、dist)
- Create: `frontend/src/main.js`
- Create: `frontend/src/App.vue`(顶栏导航 + 视图切换)
- Create: `frontend/src/style.css`(全局基础样式)

**Interfaces:**
- `vite.config.js`:插件 vue;`server.proxy`:`/api`、`/mcp`、`/a2a` → `http://localhost:8000`
- `App.vue`:state `{token, view, user}`;未登录显示 `AuthView`;已登录顶栏(知识库/对话/任务/退出)

- [x] **Step 1: 写 package.json / vite.config / index.html / main.js / style.css / App.vue 骨架**
- [x] **Step 2: `npm install` 成功;`npm run build` 成功**(先保证编译链路通)
- [x] **Step 3: 提交 `chore: scaffold vite vue frontend`**

### Task 2: API 封装 + 登录注册

**Files:**
- Create: `frontend/src/api.js`
- Create: `frontend/src/views/AuthView.vue`

**Interfaces:**
- `api.js`:`token` 存 localStorage;`request(path,{method,body,form})` 自动带 Bearer 与 JSON/FormData;导出 `login/register/listKbs/createKb/uploadDoc/listDocs/deleteDoc/listTaskRuns/listMemories/addMemory/streamChat`(SSE,回调 onEvent)
- `AuthView.vue`:登录/注册切换表单;成功后 `onAuth(token)` 进入主界面

- [x] **Step 1: 写 api.js(Auth + KB + docs + tasks + memories + streamChat SSE 解析)**
- [x] **Step 2: 写 AuthView.vue**
- [x] **Step 3: 跑 `npm run build` 确认编译通过;提交 `feat: add frontend api client and auth view`**

### Task 3: 知识库管理视图

**Files:**
- Create: `frontend/src/views/KbView.vue`

**Behavior:**
- 列表:GET `/knowledge_bases`;新建:输入名称 POST;选中库查看文档(轮询状态)
- 上传:FormData POST `/knowledge_bases/{id}/documents`;每 1.5s 轮询文档状态直到 ready/failed
- 删除文档;退出登录清理

- [x] **Step 1: 写 KbView.vue(建库/选库/上传/状态轮询/删除)**
- [x] **Step 2: build 通过,提交 `feat: add knowledge base management view`**

### Task 4: SSE 对话视图(A2A 前端主角)

**Files:**
- Create: `frontend/src/views/ChatView.vue`

**Behavior:**
- 库选择器(复用 listKbs)+ 路由选择(可选:auto/rag/summary/compare/utility)
- `streamChat(kbId, question, route, onEvent)` 解析 SSE:route→徽标、node→阶段、token→增量追加、tool→工具调用 chip、tool_result、answer→终态、sources→溯源列表(`[i]` 与回答中的 `[i]` 对应)、done→显示 conversation_id、error→红条
- "卡片视图"开关:`POST /a2ui/render`(该库+问题)拉取 A2UI 卡片 JSON,以 JSON 预览展示(对接 D6)
- 历史:显示当前会话 messages(本地数组)

- [x] **Step 1: 写 ChatView.vue(SSE 解析 + 渲染 token/route/tool/sources + A2UI 卡片)**
- [x] **Step 2: build 通过,提交 `feat: add SSE agent chat view with sources`**

### Task 5: 任务可观测视图

**Files:**
- Create: `frontend/src/views/TasksView.vue`

**Behavior:**
- GET `/task_runs` 列表:type/status/started/finished/error
- 点开某条:GET `/task_runs/{id}` 展示 `trace.events`(route/node/token/tool 时间线)

- [x] **Step 1: 写 TasksView.vue(列表 + trace 时间线)**
- [x] **Step 2: build 通过,提交 `feat: add task runs observability view`**

### Task 6: D7 收尾

- [x] **Step 1: `npm run build` 全绿;`npm run preview` 起服务,curl 首页 200 且含 `#app`**
- [x] **Step 2: 起后端(uvicorn)+ 起 vite dev,curl 经代理的 `/api/v1/health` 通**
- [x] **Step 3: 检查工作区(dist/node_modules 已忽略)、提交收尾(若有遗漏)**
