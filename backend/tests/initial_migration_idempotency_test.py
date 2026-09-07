from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.infrastructure.settings import settings
from app.main import run_database_migrations


def test_recovers_when_only_the_legacy_cameras_table_exists(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy-cameras-only.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    sync_database_url = database_url.replace("+aiosqlite", "")
    monkeypatch.setattr(settings, "database_url", database_url)

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_database_url)
    command.upgrade(alembic_config, "001_initial")

    engine = create_engine(sync_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO cameras
                        (id, name, location, model, stream_url, status, enabled)
                    VALUES
                        (1, 'legacy-camera', 'Entrance', 'Legacy', 'rtsp://legacy', 'online', 1)
                    """
                )
            )
            connection.execute(text("DROP TABLE recordings"))
            connection.execute(text("DROP TABLE alembic_version"))
    finally:
        engine.dispose()

    run_database_migrations()
    run_database_migrations()

    engine = create_engine(sync_database_url)
    try:
        inspector = inspect(engine)
        assert {
            "alembic_version",
            "cameras",
            "recordings",
            "users",
            "user_camera_access",
            "user_activity_events",
            "user_presence_sessions",
            "user_camera_alarm_preferences",
        }.issubset(inspector.get_table_names())
        assert {index["name"] for index in inspector.get_indexes("recordings")} >= {
            "ix_recordings_camera_id",
            "ix_recordings_start_time",
        }
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT name FROM cameras WHERE id = 1")) == "legacy-camera"
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "006_user_camera_alarm_preferences"
    finally:
        engine.dispose()
