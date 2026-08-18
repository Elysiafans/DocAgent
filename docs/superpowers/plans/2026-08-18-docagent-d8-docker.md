# DocAgent D8 —— 测试补强 + Docker Compose 全链路 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 按设计文档(第 227 行)落地 **Docker Compose 全链路** `frontend(nginx) + backend(uvicorn) + postgres + qdrant`,补齐一个**全链路 E2E 测试**(单测+集成+E2E 三层),并做**全量验证**:pytest 全绿 + compose build/up + 经 nginx 冒烟(首页/health/SSE 代理)。**采用设计文档的 nginx 方案**(比 D7 计划的 StaticFiles 更贴近生产,且能演示多容器编排)。

**Architecture:**
- `backend/Dockerfile`:`python:3.12-slim`,装 requirements,COPY `app`/`alembic`/`alembic.ini`/`skills`,入口 `alembic upgrade head && uvicorn`。
- `frontend/Dockerfile`:`node:20-alpine` 构建 `dist` → `nginx:alpine` 托管;`nginx.conf` 把 `/api` `/mcp` `/a2a` 反代到 `backend:8000`,SSE 需 `proxy_buffering off`。
- `docker-compose.yml` 增加 `backend` + `frontend` 服务:健康检查、`.env` 注入、数据卷、优雅停止。
- E2E 测试 `backend/tests/test_e2e.py`:一次走完 注册→登录→建库→上传→就绪→SSE 对话→溯源→task_runs→长期记忆→A2UI 卡片。

## Global Constraints

- 命令在 **WSL(Ubuntu-22.04)** 执行;后端 `conda activate yy`;前端固定 PATH(`/home/sjx_0/tools/node-v20.20.2-linux-x64/bin`,字面量,无 `$PATH`);Docker 用 **native WSL docker**(非 Docker Desktop)。
- `.env`(含密钥)永不提交、**永不 COPY 进镜像**;镜像内只靠 compose `environment` 注入。
- 测试只依赖本机基础设施(postgres+qdrant),**绝不调用真实 SiliconFlow/DeepSeek**(E2E 用 monkeypatch 注入 fake 模型/嵌入)。
- 提交信息用 conventional commits。
- 每个 Task 先 `pytest` 或 `docker build` 验证再提交。

---

### Task 1: 后端 Dockerfile

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`

**Behavior:**
- 基础镜像 `python:3.12-slim`;`pip install -r requirements.txt`;COPY 全部运行所需;`CMD sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"`
- `.dockerignore`:`__pycache__`、`*.pyc`、`.pytest_cache`、`tests/`、`.env`(密钥绝不入镜像)

- [x] **Step 1: 写 backend/Dockerfile + .dockerignore**
- [x] **Step 2: `docker build -t docagent-backend ./backend` 成功**
- [x] **Step 3: 提交 `feat: add backend dockerfile`**

### Task 2: 前端 Dockerfile + nginx

**Files:**
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Create: `frontend/.dockerignore`

**Behavior:**
- 多阶段:`node:20-alpine` 构建(`npm ci && npm run build`)→ `nginx:1.27-alpine` COPY `dist`
- `nginx.conf`:SPA `try_files`;`/api`、`/mcp`、`/a2a` → `http://backend:8000`;SSE 关键:`proxy_buffering off` + `proxy_read_timeout 300s`
- `.dockerignore`:`node_modules/`、`dist/`、`.git`

- [x] **Step 1: 写 frontend/Dockerfile + nginx.conf + .dockerignore**
- [x] **Step 2: `docker build -t docagent-frontend ./frontend` 成功**
- [x] **Step 3: 提交 `feat: add frontend dockerfile with nginx`**

### Task 3: docker-compose 全链路

**Files:**
- Modify: `docker-compose.yml`

**Behavior:**
- `backend` 服务:`build: ./backend`,`environment` 注入(postgres 主机名、qdrant 地址、密钥来自 `.env` 占位),`ports 8000:8000`,`depends_on` postgres(service_healthy),healthcheck `/api/v1/health`
- `frontend` 服务:`build: ./frontend`,`ports ${FRONTEND_PORT:-5173}:80`,`depends_on backend(service_healthy)`
- 保留 postgres/qdrant 原服务与数据卷;加优雅停止 `stop_grace_period`

- [x] **Step 1: 扩展 docker-compose.yml(backend + frontend + healthcheck + env)**
- [x] **Step 2: `docker compose config` 校验语法**
- [x] **Step 3: 提交 `feat: add full-stack docker compose`**

### Task 4: 全链路 E2E 测试

**Files:**
- Create: `backend/tests/test_e2e.py`

**Behavior:**
- 一次完整旅程(monkeypatch fake LLM/嵌入/rerank 与 D5/D6 相同):注册→登录→/auth/me→建库→PATCH 改名→上传→轮询就绪→SSE 对话(含 route/node/token/tool/answer/sources/done)→断言溯源→task_runs success→写长期记忆→search 命中→A2UI render 返回 card
- 与既有 test_agent_chat 共享 fake 注入手法,但不重复其内部断言,只验证链路贯通

- [x] **Step 1: 写 test_e2e.py(全链路旅程)**
- [x] **Step 2: `pytest -q` 全绿(新增 + 既有全部通过)**
- [x] **Step 3: 提交 `test: add full-link e2e journey test`**

### Task 5: 全量验证

- [x] **Step 1: `pytest -q` 全绿 + `npm run build` 全绿**
- [x] **Step 2: `docker compose build` 成功**
- [x] **Step 3: `docker compose up -d`;curl `:5173/`(SPA 首页 200)、`:8000/api/v1/health`(直连)、`:5173/api/v1/health`(nginx 代理)**
- [x] **Step 4: 无 token 请求 `:5173/api/v1/chat/agent` 应 401(证明 SSE 反代通)**
- [x] **Step 5: `docker compose down`(清卷可选)清理;`git status` 干净;提交收尾(若有遗漏)**
