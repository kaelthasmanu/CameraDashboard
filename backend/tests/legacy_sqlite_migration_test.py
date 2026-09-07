from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.infrastructure.settings import settings
from app.main import run_database_migrations


def test_migrates_legacy_sqlite_database_without_alembic_version(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setattr(settings, "database_url", database_url)

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url.replace("+aiosqlite", ""))
    command.upgrade(alembic_config, "001_initial")

    engine = create_engine(database_url.replace("+aiosqlite", ""))
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
    finally:
        engine.dispose()

    run_database_migrations()

    engine = create_engine(database_url.replace("+aiosqlite", ""))
    try:
        inspector = inspect(engine)
        assert {"cameras", "recordings", "users", "user_camera_access"}.issubset(inspector.get_table_names())
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "006_user_camera_alarm_preferences"
    finally:
        engine.dispose()