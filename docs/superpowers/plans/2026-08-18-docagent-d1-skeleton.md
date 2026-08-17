# DocAgent D1 —— 仓库骨架与基础设施 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭起 DocAgent 的 monorepo 骨架、FastAPI 分层后端、JSON 日志、数据库配置、Alembic 迁移与 Docker 基础设施(Postgres + QDrant),让 `uvicorn` 能跑、`/health` 能通、`alembic upgrade head` 能成功。

**Architecture:** 单仓库含 `backend/`(FastAPI 分层:core / api / db / services / rag / agents / protocols / infrastructure)与 `frontend/`(D7 再建)。后端采用应用工厂模式 + pydantic-settings 配置 + 依赖注入。基础设施用 docker-compose 提供 Postgres 与 QDrant 供本地开发。

**Tech Stack:** Python 3.11(conda env `docagent`)、FastAPI、Uvicorn、pydantic-settings、SQLAlchemy 2、psycopg3、Alembic、pytest、httpx、Docker Compose(postgres:16-alpine、qdrant)。

## Global Constraints

- 本计划所有命令在 **WSL(Ubuntu-22.04)** 内执行。仓库路径 `/home/sjx_0/project/shixi`。
- Python 环境:**conda env `yy`**(Python 3.12,已装 FastAPI 0.139 / langgraph 1.2 / langchain 1.x)。所有 python/pytest/alembic 命令带前缀:`source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy && <cmd>`。**不要创建新环境,不要降级已有包。**
- 本计划需新增依赖(装进 `yy`,见 Task 1):`SQLAlchemy`、`psycopg[binary]`、`alembic`、`pytest`、`pytest-asyncio`。
- **Docker:在 WSL 内原生安装 Docker Engine**(非 Docker Desktop 集成)。WSL 已启用 systemd(`/etc/wsl.conf`),满足运行条件。安装命令需 sudo(交互输入密码),**必须由用户本人执行**,见 Task 4。用户装完后,agent 负责验证并继续。
- `.env`(含密钥)永不提交;提交 `.env.example`。`.gitignore` 已含 `.env`。
- 本次只起 Postgres + QDrant 两个服务;backend/frontend 容器在 D8 加入 compose。
- 所有测试只依赖本机/本地基础设施,不调用任何外部 LLM API。
- 提交信息用 conventional commits(`feat:` / `fix:` / `docs:` / `chore:`)。
- 依赖管理:`requirements.txt` 记录直接依赖;已存在于 `yy` 的包按实际版本记录(不强制降级)。

---

### Task 1: 后端包骨架 + 配置模块

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/requirements.txt`
- Create: `.env.example`
- Test: `backend/tests/__init__.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Consumes: 无(本项目第一个任务)
- Produces:
  - `app.core.config.Settings`(pydantic-settings 类,含 `APP_NAME`、`DEBUG`、`API_V1_PREFIX`、`POSTGRES_*`、`QDRANT_URL`、`database_url` 属性)
  - `app.core.config.get_settings() -> Settings`(`@lru_cache` 单例)

- [ ] **Step 1: 创建目录骨架与包结构**

在 WSL 中执行:

```bash
cd /home/sjx_0/project/shixi
mkdir -p backend/app/core backend/app/api backend/app/db backend/app/models \
         backend/app/schemas backend/app/services backend/app/rag backend/app/agents \
         backend/app/protocols backend/app/infrastructure backend/tests
touch backend/app/__init__.py backend/app/core/__init__.py backend/app/api/__init__.py \
      backend/app/db/__init__.py backend/app/models/__init__.py backend/app/schemas/__init__.py \
      backend/app/services/__init__.py backend/app/rag/__init__.py backend/app/agents/__init__.py \
      backend/app/protocols/__init__.py backend/app/infrastructure/__init__.py backend/tests/__init__.py
```

- [ ] **Step 2: 确认 `yy` 环境,补齐 D1 依赖**

确认 `yy` 环境可用并查看版本:

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
python --version   # 期望 Python 3.12.x
pip show fastapi | grep -i version
```

将下面的内容写入 `backend/requirements.txt`(已存在的包按 `yy` 实际版本记录,不降级;新增的 5 个包按此版本安装):

```text
# ---- 已存在于 yy 环境(按实际版本)----
fastapi==0.139.0
uvicorn[standard]==0.51.0
pydantic==2.13.4
pydantic-settings==2.14.2
httpx==0.28.1

# ---- 本计划新增 ----
SQLAlchemy==2.0.36
psycopg[binary]==3.2.3
alembic==1.14.0
pytest==8.3.4
pytest-asyncio==0.25.0
```

安装(只新增,已存在版本会被跳过或保持):

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pip install -r backend/requirements.txt
python -c "import sqlalchemy, alembic, psycopg, pytest; print('deps OK')"
```

- [ ] **Step 3: 写配置测试(先失败)**

创建 `backend/tests/test_config.py`:

```python
from app.core.config import Settings


def test_defaults_loaded():
    settings = Settings(_env_file=None)
    assert settings.APP_NAME == "DocAgent"
    assert settings.DEBUG is False
    assert settings.API_V1_PREFIX == "/api/v1"


def test_database_url_assembled():
    settings = Settings(_env_file=None)
    assert settings.database_url == (
        "postgresql+psycopg://docagent:docagent_dev_password@localhost:5432/docagent"
    )
```

- [ ] **Step 4: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_config.py -v
```

期望:FAIL,`ModuleNotFoundError: No module named 'app'`(或 `Settings` 未定义)。

- [ ] **Step 5: 写配置实现**

创建 `backend/app/core/config.py`:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_NAME: str = "DocAgent"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # PostgreSQL
    POSTGRES_USER: str = "docagent"
    POSTGRES_PASSWORD: str = "docagent_dev_password"
    POSTGRES_DB: str = "docagent"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # QDrant
    QDRANT_URL: str = "http://localhost:6333"

    # LLM / 嵌入 / 重排提供商(D3/D5 使用,先留空)
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_CHAT_MODEL: str = "deepseek-chat"
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_config.py -v
```

期望:PASS(2 passed)。

- [ ] **Step 7: 写 `.env.example`**

创建仓库根目录 `.env.example`:

```bash
# ---- DocAgent 环境变量示例(复制为 .env 并按需修改)----

# 应用
DEBUG=false

# PostgreSQL(与 docker-compose.yml 对应)
POSTGRES_USER=docagent
POSTGRES_PASSWORD=docagent_dev_password
POSTGRES_DB=docagent
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# QDrant
QDRANT_URL=http://localhost:6333

# LLM 提供商(填入真实 key)
DEEPSEEK_API_KEY=
SILICONFLOW_API_KEY=
```

创建本地 `.env`:

```bash
cd /home/sjx_0/project/shixi
cp .env.example .env
```

- [ ] **Step 8: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app backend/requirements.txt backend/tests .env.example
git commit -m "feat: scaffold FastAPI backend with config module"
```

---

### Task 2: 结构化 JSON 日志

**Files:**
- Create: `backend/app/core/logging.py`
- Test: `backend/tests/test_logging.py`

**Interfaces:**
- Consumes: 无(纯标准库)
- Produces: `app.core.logging.JsonFormatter`(logging.Formatter)、`app.core.logging.setup_logging(level: int = logging.INFO) -> None`

- [ ] **Step 1: 写日志测试(先失败)**

创建 `backend/tests/test_logging.py`:

```python
import json
import logging

from app.core.logging import JsonFormatter


def test_json_formatter_emits_structured_record():
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello {name}",
        args={"name": "docagent"},
        exc_info=None,
    )
    formatted = JsonFormatter().format(record)
    parsed = json.loads(formatted)
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "hello docagent"
    assert parsed["timestamp"]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_logging.py -v
```

期望:FAIL,`ModuleNotFoundError: No module named 'app.core.logging'`。

- [ ] **Step 3: 写日志实现**

创建 `backend/app/core/logging.py`:

```python
import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_logging.py -v
```

期望:PASS。

- [ ] **Step 5: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/core/logging.py backend/tests/test_logging.py
git commit -m "feat: add structured JSON logging"
```

---

### Task 3: FastAPI 应用工厂 + `/health` 端点

**Files:**
- Create: `backend/app/api/health.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Consumes: `Settings` / `get_settings`(Task 1)、`setup_logging`(Task 2)
- Produces: `app.main.app`(FastAPI 实例,含 `/api/v1/health`)、`app.main.create_app() -> FastAPI`、`app.api.health.router`

- [ ] **Step 1: 写健康检查测试(先失败)**

创建 `backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_health.py -v
```

期望:FAIL,`ModuleNotFoundError: No module named 'app.main'`。

- [ ] **Step 3: 写健康检查路由**

创建 `backend/app/api/health.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 4: 写应用工厂**

创建 `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.logging import setup_logging


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()
    app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)
    app.include_router(health_router, prefix=settings.API_V1_PREFIX)
    return app


app = create_app()
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_health.py -v
```

期望:PASS。

- [ ] **Step 6: 手动启动 uvicorn 验证**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
nohup uvicorn app.main:app --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 2
curl -s http://localhost:8000/api/v1/health
# 期望:{"status":"ok"}
kill %1
```

- [ ] **Step 7: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/main.py backend/app/api/health.py backend/tests/test_health.py
git commit -m "feat: add FastAPI app factory with health endpoint"
```

---

### Task 4: 原生安装 Docker Engine(WSL)+ Compose 基础设施

**Files:**
- Create: `docker-compose.yml`

**Interfaces:**
- Consumes: `.env`(Task 1,由 compose 读取做变量替换)
- Produces: WSL 内可用的 Docker Engine + 本地 Postgres(5432)与 QDrant(6333)服务;后续任务与容器(backend/frontend)都依赖

> ⚠️ **本任务 Step 1 必须由用户本人执行**(需要 sudo 密码,agent 无法代替)。WSL 已启用 systemd(`/etc/wsl.conf`),满足原生运行条件。

- [ ] **Step 1(用户执行):在 WSL 内安装 Docker Engine**

在 WSL 终端里执行(遇到密码提示输入你的 sudo 密码):

```bash
# 1) 移除可能冲突的旧包
sudo apt-get remove -y docker docker-engine docker.io containerd runc

# 2) 安装依赖并添加 Docker 官方 apt 源
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 3) 安装 Docker 引擎 + compose 插件
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 4) 把当前用户加入 docker 组(之后免 sudo)
sudo usermod -aG docker $USER

# 5) 启动 docker 服务(systemd 已启用)
sudo systemctl enable --now docker
```

完成后**新开一个 WSL 终端**(让 `docker` 组生效),执行验证:

```bash
docker --version        # 期望 Docker version 2x.x
docker compose version  # 期望 Docker Compose version v2.x
sudo systemctl is-active docker   # 期望 active
docker ps               # 期望无报错(空列表即可)
```

把验证输出告诉 agent(或直接回复"已装好"),由 agent 继续 Step 2 及后续步骤。

- [ ] **Step 2(agent 执行):写 docker-compose.yml**

创建仓库根目录 `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: docagent-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-docagent}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-docagent_dev_password}
      POSTGRES_DB: ${POSTGRES_DB:-docagent}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-docagent}"]
      interval: 5s
      timeout: 3s
      retries: 10

  qdrant:
    image: qdrant/qdrant:v1.13.0
    container_name: docagent-qdrant
    ports:
      - "${QDRANT_PORT:-6333}:6333"
    volumes:
      - qdrant_storage:/qdrant/storage

volumes:
  pgdata:
  qdrant_storage:
```

- [ ] **Step 3(agent 执行):启动并验证 Postgres 与 QDrant**

```bash
cd /home/sjx_0/project/shixi
docker compose up -d postgres qdrant
docker compose ps   # 两个容器都应显示 healthy / running
```

验证连通性:

```bash
docker exec docagent-postgres pg_isready -U docagent
# 期望:accepting connections
curl -s http://localhost:6333/collections
# 期望:{"result":{"collections":[]},"status":"ok",...}
```

- [ ] **Step 4: 提交**

```bash
cd /home/sjx_0/project/shixi
git add docker-compose.yml
git commit -m "chore: add docker-compose for postgres and qdrant dev services"
```

---

### Task 5: SQLAlchemy 会话 + Alembic 基线迁移

**Files:**
- Create: `backend/app/db/session.py`
- Create: `backend/app/db/base.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`(Alembic 生成的模板,按下方修改)
- Create: `backend/alembic/versions/0001_baseline.py`
- Test: `backend/tests/test_db_session.py`

**Interfaces:**
- Consumes: `Settings.database_url`(Task 1)、Postgres 服务(Task 4)
- Produces:
  - `app.db.base.Base`(SQLAlchemy `DeclarativeBase`)
  - `app.db.session.engine`、`app.db.session.SessionLocal`、`app.db.session.get_db()`
  - Alembic 基线迁移,`alembic upgrade head` 后 `alembic_version` 表存在

- [ ] **Step 1: 写数据库会话测试(先失败)**

创建 `backend/tests/test_db_session.py`:

```python
from sqlalchemy import text

from app.db.session import SessionLocal


def test_db_connectivity_and_version_table():
    with SessionLocal() as db:
        result = db.execute(text("SELECT 1")).scalar_one()
        assert result == 1
        # Alembic 基线迁移后应存在版本表
        version = db.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert version
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_db_session.py -v
```

期望:FAIL,`ModuleNotFoundError: No module named 'app.db.session'`。

- [ ] **Step 3: 写 Base 与会话**

创建 `backend/app/db/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

创建 `backend/app/db/session.py`:

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: 初始化 Alembic 并配置 env.py**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
alembic init alembic
```

编辑 `backend/alembic/env.py`,把 `target_metadata` 与 `sqlalchemy.url` 指向我们的 Base 与配置,并把项目根加入 `sys.path`。**用下面内容整体替换整个文件**(不要沿用模板内容):

```python
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

# 确保能 import app 包(无论从哪个目录执行 alembic)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine

    connectable = create_engine(config.get_main_option("sqlalchemy.url"))
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

> 注意:若 `alembic.ini` 中的 `script_location` 需要相对路径,保持默认即可(`alembic.ini` 与 `alembic/` 都在 `backend/` 下,从 `backend/` 运行命令)。

- [ ] **Step 5: 生成基线迁移并执行 upgrade**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
alembic revision -m "baseline"   # 空迁移,记录版本起点
alembic upgrade head
alembic current   # 期望输出:0001 (head) 或类似
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_db_session.py -v
```

期望:PASS。

- [ ] **Step 7: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/db backend/alembic backend/alembic.ini backend/tests/test_db_session.py
git commit -m "feat: add sqlalchemy session and alembic baseline migration"
```

---

### Task 6: D1 收尾 —— 全量验证 + 提交

**Files:**
- 无新增(验证与收尾)

**Interfaces:**
- Consumes: 全部 Task 1-5 产物

- [ ] **Step 1: 全量测试**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest -v
```

期望:全部 PASS(4 个测试文件)。

- [ ] **Step 2: 再次确认关键服务**

```bash
cd /home/sjx_0/project/shixi
docker compose ps
curl -s http://localhost:6333/collections
```

期望:postgres/qdrant 均 healthy/running;collections 接口返回 ok。

- [ ] **Step 3: 检查工作区状态**

```bash
cd /home/sjx_0/project/shixi
git status
git log --oneline
```

期望:工作区干净;log 显示 D1 的 5 个 commit(`feat: scaffold...` → `feat: add sqlalchemy...`)。

- [ ] **Step 4: 收尾提交(若 Step 3 有未提交改动)**

```bash
cd /home/sjx_0/project/shixi
git add -A
git commit -m "chore: complete D1 skeleton milestone" || echo "无待提交改动"
```
