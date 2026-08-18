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
