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
            conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
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
