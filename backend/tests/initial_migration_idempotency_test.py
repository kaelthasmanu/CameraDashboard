from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.infrastructure.database import Base
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


def test_replays_all_migrations_when_schema_exists_without_revision_history(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy-current-schema.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    sync_database_url = database_url.replace("+aiosqlite", "")
    monkeypatch.setattr(settings, "database_url", database_url)

    engine = create_engine(sync_database_url)
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users
                        (id, username, password_hash, is_active, is_admin, role)
                    VALUES
                        (1, 'legacy-guard', 'hash', 1, 0, 'guardia')
                    """
                )
            )
            connection.execute(text("DROP INDEX ix_user_activity_events_event_type"))
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
        assert {index["name"] for index in inspector.get_indexes("users")} >= {
            "ix_users_username",
        }
        assert {index["name"] for index in inspector.get_indexes("user_activity_events")} >= {
            "ix_user_activity_events_user_id",
            "ix_user_activity_events_event_type",
            "ix_user_activity_events_camera_name",
            "ix_user_activity_events_occurred_at",
        }
        assert {index["name"] for index in inspector.get_indexes("user_presence_sessions")} >= {
            "ix_user_presence_sessions_user_id",
            "ix_user_presence_sessions_last_seen_at",
        }
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT role FROM users WHERE id = 1")) == "guardia"
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "006_user_camera_alarm_preferences"
    finally:
        engine.dispose()


def test_adds_role_and_backfills_legacy_users_without_revision_history(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy-users.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    sync_database_url = database_url.replace("+aiosqlite", "")
    monkeypatch.setattr(settings, "database_url", database_url)

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_database_url)
    command.upgrade(alembic_config, "002_users")

    engine = create_engine(sync_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (id, username, password_hash, is_active, is_admin)
                    VALUES
                        (1, 'legacy-admin', 'hash', 1, 1),
                        (2, 'legacy-user', 'hash', 1, 0)
                    """
                )
            )
            connection.execute(text("DROP TABLE alembic_version"))
    finally:
        engine.dispose()

    run_database_migrations()

    engine = create_engine(sync_database_url)
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT username, role FROM users ORDER BY id")
            ).tuples().all() == [
                ("legacy-admin", "admin"),
                ("legacy-user", "supervisor"),
            ]
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "006_user_camera_alarm_preferences"
    finally:
        engine.dispose()
