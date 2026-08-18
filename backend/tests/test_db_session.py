from app.db.session import SessionLocal
from sqlalchemy import text


def test_db_connectivity_and_version_table():
    with SessionLocal() as db:
        result = db.execute(text("SELECT 1")).scalar_one()
        assert result == 1
        # Alembic 基线迁移后应存在版本表
        version = db.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert version
