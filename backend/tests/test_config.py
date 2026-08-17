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
