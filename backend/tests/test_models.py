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
