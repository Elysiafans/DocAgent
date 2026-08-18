# DocAgent D9 —— README + CI + GitHub 上传 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按设计文档 D9 交付:README(项目介绍、Mermaid 架构图、**功能↔岗位要求对照表**、快速开始、目录结构、未来计划)+ GitHub Actions CI(lint + test + build)+ 推送到 `git@github.com:Elysiafans/DocAgent.git`。README 是本作品的一部分(求职展示)。

**现状核对:** 后端 95 个 pytest 全绿、前端 `npm run build` 绿、Docker Compose 全链路已验证;commit 历史约 60 个、全部为 `sjx_0 <sjx_0@local>`;无 git remote、无 SSH 密钥(已生成,待用户加公钥);**提交身份将重写为 Elysiafans + 用户邮箱**(用户已确认重写)。

**Architecture:**
- `README.md`:按实际实现(D1–D8)而非设计蓝本撰写——前端为纯 Vue3+Vite(无 router/pinia),四智能体为 rag/summary/compare/utility,工具 5 个(knowledge_search/calculator/web_search/load_skill/compare_documents)。
- `.github/workflows/ci.yml`:backend tests(services: postgres + qdrant)+ frontend build + docker build + lint(视 ruff 检查结果决定)。
- 推送前统一 `git filter-branch` 重写作者/提交者 → 配置 remote → push。

## Global Constraints

- README 用中文,准确反映已实现能力,不夸大设计蓝本中未做的项(如 Pinia/router、代码解答员)。
- CI 在 GitHub Actions 跑:**不依赖真实 LLM/嵌入 API**(测试全 fake);postgres/qdrant 用 `services:` 起;`_ensure_test_db` 会自动建 `docagent_test`。
- `.env` 永不提交;README 只给 `.env.example` 指引。
- 命令:后端 `conda activate yy`;前端固定 PATH;git 在 UNC 路径执行。
- 提交信息 conventional commits;最终一次整体重写身份后 push。

---

### Task 1: README.md

**Files:**
- Create: `README.md`

**Content:**
- 标题 + 一句话定位 + 徽章(CI)
- Mermaid 架构图(nginx/前端/FastAPI/服务层/领域层/Postgres+QDrant)
- 核心能力清单(D1–D8 实际实现:多智能体编排/混合检索重排/流式 SSE/协议 MCP+A2A/A2UI/长期记忆/可观测/Docker 全链路)
- **功能 ↔ 岗位要求对照表**(AI 应用开发工程师:RAG 落地 / 智能体编排 / 协议工程 / 前端对接 / 工程化 CI/CD)
- 快速开始(Docker Compose 一行起 + 本地开发两套流程)
- API 一览(按模块表格)
- 目录结构
- 测试与 CI
- 配置说明(.env.example)
- 未来计划

- [x] **Step 1: 写 README.md(含 Mermaid 架构图 + 对照表)**
- [x] **Step 2: 提交 `docs: add comprehensive readme`**

### Task 2: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

**Behavior:**
- Job `backend-tests`:`services` 起 postgres:16 + qdrant:v1.13.0,python 3.12,`pip install -r requirements.txt`,`pytest -q`
- Job `frontend-build`:node 20,`npm ci`,`npm run build`
- Job `docker-build`:build backend + frontend 镜像
- Job `lint`(视 ruff 结果):`ruff check backend/app backend/tests`

- [x] **Step 1: 写 ci.yml(services + 多 job)**
- [x] **Step 2: 本地等价验证(pytest/npm build 已绿;ruff 已修至全绿)**
- [x] **Step 3: 提交 `ci: add github actions workflow`**

### Task 3: 身份重写 + 推送 GitHub

- [ ] **Step 1: 用用户邮箱重写全部提交作者/提交者为 Elysiafans**
- [ ] **Step 2: 配置 remote `git@github.com:Elysiafans/DocAgent.git` + SSH 测试**
- [ ] **Step 3: `git push -u origin main` 成功;`git ls-remote` 验证远端有内容**
- [ ] **Step 4: 清理(临时分支/过滤缓存);`git status` 干净;提交收尾(若有)**
