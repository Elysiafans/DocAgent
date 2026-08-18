# DocAgent D2 —— 数据模型 + JWT 鉴权 + 知识库 CRUD 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建齐全部 7 张业务表(users/knowledge_bases/documents/doc_chunks/conversations/messages/task_runs),实现 JWT 注册/登录鉴权,并提供知识库 CRUD API,全部有测试覆盖。

**Architecture:** SQLAlchemy 2.0 声明式模型 + Alembic 自动迁移;`core/security.py` 封装 bcrypt 哈希与 JWT;`api/deps.py` 提供 `get_current_user` 依赖;API 分层(路由 → Service → 模型)。新增**测试专用数据库 `docagent_test`**(conftest 自动建库并跑迁移),让测试不污染开发库。

**Tech Stack:** 沿用 D1。新增依赖:`passlib`(bcrypt 哈希)、`email-validator`(EmailStr)。

## Global Constraints

- 沿用 D1 约束:WSL 内执行、`yy` 环境、命令前缀 `source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy && <cmd>`。
- Postgres 与 QDrant 容器需运行中(`docker compose ps` 确认)。若未运行:`cd /home/sjx_0/project/shixi && docker compose up -d postgres qdrant`。
- 测试全部跑在 `docagent_test` 库(conftest 自动创建并跑 Alembic 迁移),不污染 `docagent` 开发库。
- 密钥永不入库:`.env` 已 gitignore;`SECRET_KEY` 默认值仅限开发。
- 迁移命令从 `backend/` 目录执行。新表必须通过 `alembic revision --autogenerate` 生成,不用手写。
- 提交信息用 conventional commits。
- 模型一律 SQLAlchemy 2.0 `Mapped[...]` / `mapped_column()` 风格。

---

### Task 1: 配置修正 + 测试数据库基础设施

**Files:**
- Modify: `backend/app/core/config.py`(.env 改为绝对路径)
- Modify: `backend/tests/test_config.py`(测试与外部 env 解耦)
- Create: `backend/tests/conftest.py`(测试库 + 迁移 + fixtures)
- Test: 现有 `tests/test_*.py` 全部通过

**Interfaces:**
- Consumes: D1 的 Settings / session / alembic
- Produces:
  - `tests/conftest.py` 提供 fixtures:`client`(TestClient)、`clean_tables`(每测试后清空)、会话级 `migrate_test_db`
  - Settings 从仓库根 `.env` 读取(绝对路径)

- [ ] **Step 1: 修复 config.py 的 .env 路径为绝对路径**

问题:`.env` 在仓库根,而 uvicorn/pytest 从 `backend/` 运行,相对路径 `env_file=".env"` 读不到 → 密钥/配置会静默丢失。

编辑 `backend/app/core/config.py`,把 `model_config` 改为:

```python
from pathlib import Path

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# 仓库根目录的 .env(backends/app/core/config.py 向上 4 级)
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )
```

其余字段保持不变。

- [ ] **Step 2: 让 test_config 与外部环境解耦**

编辑 `backend/tests/test_config.py` 的两个测试,加 `monkeypatch` 清理数据库相关环境变量(否则 D2 的 conftest 设置 `POSTGRES_DB=docagent_test` 会让断言失败):

```python
from app.core.config import Settings

_DB_ENV_KEYS = [
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "SECRET_KEY",
]


def test_defaults_loaded(monkeypatch):
    for k in _DB_ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    settings = Settings(_env_file=None)
    assert settings.APP_NAME == "DocAgent"
    assert settings.DEBUG is False
    assert settings.API_V1_PREFIX == "/api/v1"


def test_database_url_assembled(monkeypatch):
    for k in _DB_ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url == (
        "postgresql+psycopg://docagent:docagent_dev_password@localhost:5432/docagent"
    )
```

- [ ] **Step 3: 写 conftest.py(测试库 + 迁移 + fixtures)**

创建 `backend/tests/conftest.py`:

```python
import os
from pathlib import Path

# 必须在导入任何 app 模块之前设置,让 get_settings() 读到测试库
os.environ["POSTGRES_DB"] = "docagent_test"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app import models  # noqa: E402, F401  确保模型注册到 Base.metadata
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402

TEST_DB_NAME = "docagent_test"
_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _ensure_test_db() -> None:
    admin_url = (
        "postgresql+psycopg://docagent:docagent_dev_password@localhost:5432/postgres"
    )
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": TEST_DB_NAME},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE {TEST_DB_NAME}'))
    admin_engine.dispose()


def _run_migrations() -> None:
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")


_ensure_test_db()


@pytest.fixture(scope="session", autouse=True)
def migrate_test_db():
    _run_migrations()
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def client():
    return TestClient(app)
```

- [ ] **Step 4: 运行现有测试,确认 5 个全过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest -v
```

期望:5 passed(test_config 2 / test_logging 1 / test_health 1 / test_db_session 1,全部打到 `docagent_test` 库)。若 test_db_session 报 `alembic_version` 不存在,说明迁移未跑,检查 conftest 的 `_run_migrations`。

- [ ] **Step 5: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/core/config.py backend/tests/test_config.py backend/tests/conftest.py
git commit -m "test: isolate tests to docagent_test db and fix .env path"
```

---

### Task 2: 全部数据模型 + Alembic 自动迁移

**Files:**
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/knowledge_base.py`
- Create: `backend/app/models/document.py`
- Create: `backend/app/models/chunk.py`
- Create: `backend/app/models/conversation.py`
- Create: `backend/app/models/message.py`
- Create: `backend/app/models/task_run.py`
- Modify: `backend/app/models/__init__.py`(导入全部模型)
- Modify: `backend/alembic/env.py`(import app.models 注册表)
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `app.db.base.Base`
- Produces: 7 张表及其 ORM 类,供 Service/Alembic 使用
  - `User(id, email, hashed_password, created_at)`
  - `KnowledgeBase(id, name, description, owner_id, chunk_strategy, chunk_size, chunk_overlap, created_at)`
  - `Document(id, kb_id, name, file_type, size, status, progress, stage, chunk_count, error, created_at)`
  - `DocChunk(id, doc_id, chunk_index, content, char_count, hash, meta, created_at)`
  - `Conversation(id, user_id, kb_id, title, created_at)`
  - `Message(id, conv_id, role, content, sources, agent_type, created_at)`
  - `TaskRun(id, type, status, error, trace, started_at, finished_at)`

- [ ] **Step 1: 写各模型文件**

`backend/app/models/user.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

`backend/app/models/knowledge_base.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500), default="")
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True
    )
    chunk_strategy: Mapped[str] = mapped_column(String(30), default="recursive")
    chunk_size: Mapped[int] = mapped_column(default=800)
    chunk_overlap: Mapped[int] = mapped_column(default=100)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

`backend/app/models/document.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    kb_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(20))
    size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="uploading")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str] = mapped_column(String(20), default="parse")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

`backend/app/models/chunk.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocChunk(Base):
    __tablename__ = "doc_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # 页码/标题层级/偏移
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

`backend/app/models/conversation.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kb_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="新会话")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

`backend/app/models/message.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conv_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # 溯源
    agent_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

`backend/app/models/task_run.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TaskRun(Base):
    __tablename__ = "task_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 2: 更新 models/__init__.py 导入全部模型**

覆盖 `backend/app/models/__init__.py`:

```python
from app.models.chunk import DocChunk
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.message import Message
from app.models.task_run import TaskRun
from app.models.user import User

__all__ = [
    "DocChunk",
    "Conversation",
    "Document",
    "KnowledgeBase",
    "Message",
    "TaskRun",
    "User",
]
```

- [ ] **Step 3: env.py 注册模型(让 autogenerate 看到表)**

编辑 `backend/alembic/env.py`,在 `from app.db.base import Base` 之后加一行:

```python
from app import models  # noqa: F401  确保模型注册到 Base.metadata
```

- [ ] **Step 4: 自动生成迁移并执行**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
alembic revision --autogenerate -m "add core tables"
alembic upgrade head
alembic current   # 期望显示新 revision (head)
```

检查生成的迁移文件里包含 7 张表的 `create_table`(尤其 `doc_chunks`、`messages` 的 JSONB 列)。

- [ ] **Step 5: 写模型测试(验证 7 表已建)**

创建 `backend/tests/test_models.py`:

```python
from sqlalchemy import inspect

from app.db.session import engine

EXPECTED_TABLES = {
    "alembic_version",
    "users",
    "knowledge_bases",
    "documents",
    "doc_chunks",
    "conversations",
    "messages",
    "task_runs",
}


def test_all_core_tables_created():
    names = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES.issubset(names)
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_models.py -v
```

期望:1 passed。

- [ ] **Step 7: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/models backend/alembic backend/tests/test_models.py
git commit -m "feat: add core data models with alembic migration"
```

---

### Task 3: JWT 安全模块

**Files:**
- Modify: `backend/requirements.txt`(加 passlib、email-validator)
- Modify: `backend/app/core/config.py`(加 SECRET_KEY / ALGORITHM / ACCESS_TOKEN_EXPIRE_MINUTES)
- Modify: `.env.example`(加 SECRET_KEY)
- Create: `backend/app/core/security.py`
- Test: `backend/tests/test_security.py`

**Interfaces:**
- Consumes: `Settings`
- Produces:
  - `app.core.security.hash_password(password: str) -> str`
  - `app.core.security.verify_password(plain: str, hashed: str) -> bool`
  - `app.core.security.create_access_token(subject: str) -> str`
  - `app.core.security.decode_access_token(token: str) -> dict`

- [ ] **Step 1: 安装依赖并更新 requirements.txt**

在 `backend/requirements.txt` 追加:

```text

# ---- D2 新增 ----
passlib==1.7.4
email-validator==2.2.0
```

安装:

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pip install -r requirements.txt
```

- [ ] **Step 2: 写安全测试(先失败)**

创建 `backend/tests/test_security.py`:

```python
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong-pass", hashed)


def test_token_roundtrip():
    token = create_access_token("42")
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_security.py -v
```

期望:FAIL,`ModuleNotFoundError: No module named 'app.core.security'`。

- [ ] **Step 4: 给 Settings 加 JWT 配置**

编辑 `backend/app/core/config.py`,在 `API_V1_PREFIX` 之后加:

```python
    # JWT
    SECRET_KEY: str = "dev-secret-change-me-in-prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天
```

在 `.env.example` 追加:

```bash
# JWT 密钥(生产必须更换)
SECRET_KEY=dev-secret-change-me-in-prod
```

- [ ] **Step 5: 写 security.py 实现**

创建 `backend/app/core/security.py`:

```python
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_security.py -v
```

期望:2 passed。若出现 `AttributeError: module 'bcrypt' has no attribute '__about__'` 类警告,是 passlib+bcrypt4 的已知问题,可忽略;功能正常即可。

- [ ] **Step 7: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/requirements.txt backend/app/core/config.py backend/app/core/security.py .env.example backend/tests/test_security.py
git commit -m "feat: add JWT auth and password hashing"
```

---

### Task 4: 用户注册 / 登录 / 当前用户 API

**Files:**
- Create: `backend/app/schemas/__init__.py`(若为空则保留)
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/services/user_service.py`
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/main.py`(挂载 auth 路由)
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `User` 模型、`security` 模块、`get_db`
- Produces:
  - `POST /api/v1/auth/register` → 201 `UserOut`
  - `POST /api/v1/auth/login` → 200 `Token`
  - `GET /api/v1/auth/me` → 200 `UserOut`(需 Bearer)
  - `app.api.deps.get_current_user`(供后续所有受保护路由复用)

- [ ] **Step 1: 写鉴权测试(先失败)**

创建 `backend/tests/test_auth.py`:

```python
import pytest


def _register(client, email="a@test.com", password="password123"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )


def test_register_login_me(client):
    r = _register(client)
    assert r.status_code == 201
    assert r.json()["email"] == "a@test.com"
    assert "hashed_password" not in r.json()

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "a@test.com", "password": "password123"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "a@test.com"


def test_register_duplicate_email(client):
    assert _register(client).status_code == 201
    assert _register(client).status_code == 409


def test_login_wrong_password(client):
    _register(client)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "a@test.com", "password": "wrongpass"},
    )
    assert r.status_code == 401


def test_me_unauthenticated(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        ).status_code
        == 401
    )
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_auth.py -v
```

期望:FAIL,`404 Not Found`(路由未挂载)。

- [ ] **Step 3: 写 schemas/auth.py**

创建 `backend/app/schemas/auth.py`:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 4: 写 api/deps.py**

创建 `backend/app/api/deps.py`:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
```

- [ ] **Step 5: 写 services/user_service.py**

创建 `backend/app/services/user_service.py`:

```python
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import LoginRequest, UserCreate


def register_user(db: Session, payload: UserCreate) -> User:
    exists = db.execute(
        select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(db: Session, payload: LoginRequest) -> dict:
    user = db.execute(
        select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    return {"access_token": create_access_token(str(user.id)), "token_type": "bearer"}
```

- [ ] **Step 6: 写 api/auth.py**

创建 `backend/app/api/auth.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, Token, UserCreate, UserOut
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    return user_service.register_user(db, payload)


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    return user_service.login(db, payload)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
```

- [ ] **Step 7: main.py 挂载 auth 路由**

编辑 `backend/app/main.py`,在 health 路由之后加:

```python
from app.api.auth import router as auth_router

# create_app 内,health 路由之后:
    app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
```

- [ ] **Step 8: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_auth.py -v
```

期望:4 passed。

- [ ] **Step 9: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/schemas backend/app/api backend/app/services backend/app/main.py backend/tests/test_auth.py
git commit -m "feat: add register/login/me endpoints with JWT"
```

---

### Task 5: 知识库 CRUD API

**Files:**
- Create: `backend/app/schemas/knowledge_base.py`
- Create: `backend/app/services/knowledge_base_service.py`
- Create: `backend/app/api/knowledge_bases.py`
- Modify: `backend/app/main.py`(挂载 knowledge_bases 路由)
- Test: `backend/tests/test_knowledge_bases.py`

**Interfaces:**
- Consumes: `get_current_user`、`KnowledgeBase` 模型、`get_db`
- Produces:
  - `POST /api/v1/knowledge_bases` → 201 `KnowledgeBaseOut`
  - `GET /api/v1/knowledge_bases` → 200 `list[KnowledgeBaseOut]`
  - `GET /api/v1/knowledge_bases/{id}` → 200 `KnowledgeBaseOut`(404 若非本人)
  - `PATCH /api/v1/knowledge_bases/{id}` → 200 `KnowledgeBaseOut`
  - `DELETE /api/v1/knowledge_bases/{id}` → 204

- [ ] **Step 1: 写 CRUD 测试(先失败)**

创建 `backend/tests/test_knowledge_bases.py`:

```python
def _auth_headers(client, email="u@test.com", password="password123"):
    client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    r = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_create_list_get_kb(client):
    h = _auth_headers(client)
    r = client.post(
        "/api/v1/knowledge_bases",
        json={"name": "我的知识库", "description": "测试知识库"},
        headers=h,
    )
    assert r.status_code == 201
    kb = r.json()
    assert kb["name"] == "我的知识库"
    assert kb["chunk_strategy"] == "recursive"
    assert kb["chunk_size"] == 800

    assert len(client.get("/api/v1/knowledge_bases", headers=h).json()) == 1
    assert client.get(f"/api/v1/knowledge_bases/{kb['id']}", headers=h).json()["id"] == kb["id"]


def test_update_delete_kb(client):
    h = _auth_headers(client)
    kb_id = client.post(
        "/api/v1/knowledge_bases", json={"name": "A"}, headers=h
    ).json()["id"]

    r = client.patch(
        f"/api/v1/knowledge_bases/{kb_id}",
        json={"name": "B", "chunk_size": 500},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "B"
    assert r.json()["chunk_size"] == 500

    assert client.delete(f"/api/v1/knowledge_bases/{kb_id}", headers=h).status_code == 204
    assert client.get(f"/api/v1/knowledge_bases/{kb_id}", headers=h).status_code == 404


def test_cannot_access_others_kb(client):
    h1 = _auth_headers(client, email="u1@test.com")
    h2 = _auth_headers(client, email="u2@test.com")
    kb_id = client.post(
        "/api/v1/knowledge_bases", json={"name": "private"}, headers=h1
    ).json()["id"]

    assert client.get(f"/api/v1/knowledge_bases/{kb_id}", headers=h2).status_code == 404
    assert (
        client.delete(f"/api/v1/knowledge_bases/{kb_id}", headers=h2).status_code
        == 404
    )


def test_kb_requires_auth(client):
    assert client.get("/api/v1/knowledge_bases").status_code == 401
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_knowledge_bases.py -v
```

期望:FAIL(路由未挂载)。

- [ ] **Step 3: 写 schemas/knowledge_base.py**

创建 `backend/app/schemas/knowledge_base.py`:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChunkStrategy = Literal["recursive", "markdown_header"]


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    chunk_strategy: ChunkStrategy = "recursive"
    chunk_size: int = Field(default=800, ge=100, le=2000)
    chunk_overlap: int = Field(default=100, ge=0, le=500)


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    chunk_strategy: ChunkStrategy | None = None
    chunk_size: int | None = Field(default=None, ge=100, le=2000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=500)


class KnowledgeBaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    owner_id: int
    chunk_strategy: str
    chunk_size: int
    chunk_overlap: int
    created_at: datetime
```

- [ ] **Step 4: 写 services/knowledge_base_service.py**

创建 `backend/app/services/knowledge_base_service.py`:

```python
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeBase, User
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate


def list_knowledge_bases(db: Session, user: User) -> list[KnowledgeBase]:
    return list(
        db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.owner_id == user.id)
            .order_by(KnowledgeBase.id)
        ).scalars()
    )


def get_owned_knowledge_base(db: Session, user: User, kb_id: int) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None or kb.owner_id != user.id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Knowledge base not found"
        )
    return kb


def create_knowledge_base(
    db: Session, user: User, payload: KnowledgeBaseCreate
) -> KnowledgeBase:
    kb = KnowledgeBase(owner_id=user.id, **payload.model_dump())
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def update_knowledge_base(
    db: Session, user: User, kb_id: int, payload: KnowledgeBaseUpdate
) -> KnowledgeBase:
    kb = get_owned_knowledge_base(db, user, kb_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(kb, field, value)
    db.commit()
    db.refresh(kb)
    return kb


def delete_knowledge_base(db: Session, user: User, kb_id: int) -> None:
    kb = get_owned_knowledge_base(db, user, kb_id)
    db.delete(kb)
    db.commit()
```

- [ ] **Step 5: 写 api/knowledge_bases.py**

创建 `backend/app/api/knowledge_bases.py`:

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import KnowledgeBase, User
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
)
from app.services import knowledge_base_service

router = APIRouter(prefix="/knowledge_bases", tags=["knowledge_bases"])


@router.get("", response_model=list[KnowledgeBaseOut])
def list_kbs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[KnowledgeBase]:
    return knowledge_base_service.list_knowledge_bases(db, current_user)


@router.post("", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
def create_kb(
    payload: KnowledgeBaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeBase:
    return knowledge_base_service.create_knowledge_base(db, current_user, payload)


@router.get("/{kb_id}", response_model=KnowledgeBaseOut)
def get_kb(
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeBase:
    return knowledge_base_service.get_owned_knowledge_base(db, current_user, kb_id)


@router.patch("/{kb_id}", response_model=KnowledgeBaseOut)
def update_kb(
    kb_id: int,
    payload: KnowledgeBaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeBase:
    return knowledge_base_service.update_knowledge_base(
        db, current_user, kb_id, payload
    )


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kb(
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    knowledge_base_service.delete_knowledge_base(db, current_user, kb_id)
```

- [ ] **Step 6: main.py 挂载 knowledge_bases 路由**

编辑 `backend/app/main.py`,追加:

```python
from app.api.knowledge_bases import router as knowledge_bases_router

# create_app 内:
    app.include_router(knowledge_bases_router, prefix=settings.API_V1_PREFIX)
```

- [ ] **Step 7: 运行测试确认通过**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest tests/test_knowledge_bases.py -v
```

期望:4 passed。

- [ ] **Step 8: 提交**

```bash
cd /home/sjx_0/project/shixi
git add backend/app/schemas backend/app/services backend/app/api backend/app/main.py backend/tests/test_knowledge_bases.py
git commit -m "feat: add knowledge base CRUD API"
```

---

### Task 6: D2 收尾 —— 全量验证 + 提交

**Files:**
- 无新增(验证与收尾)

- [ ] **Step 1: 全量测试**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
pytest -v
```

期望:全部 PASS(约 16 个测试)。

- [ ] **Step 2: 确认迁移与开发库**

```bash
cd /home/sjx_0/project/shixi/backend
source ~/miniconda3/etc/profile.d/conda.sh && conda activate yy
alembic current
```

期望:显示最新的 D2 migration (head)。开发库 `docagent` 也会被同样迁移(可选:`alembic upgrade head` 已对开发库执行过)。

- [ ] **Step 3: 检查工作区**

```bash
cd /home/sjx_0/project/shixi
git status
git log --oneline
```

期望:工作区干净(除 `.env` 与缓存外);log 显示 D2 的 5 个 commit。

- [ ] **Step 4: 收尾提交(若有遗漏)**

```bash
cd /home/sjx_0/project/shixi
git add -A
git commit -m "chore: complete D2 models and auth milestone" || echo "无待提交改动"
```
