"""Contract tests for the administrator-only user activity audit.

The tests use a throwaway SQLite database so the presence calculation and the
audit event are exercised with the same SQL queries used in production.  They
do not depend on the project database or on MediaMTX.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.camera import Camera, CameraStatus
from app.infrastructure.database import Base
from app.infrastructure.db_models import (
    UserActivityEventModel,
    UserCameraAccessModel,
    UserModel,
    UserPresenceSessionModel,
)
from app.infrastructure.security import (
    get_current_user,
    get_session,
    hash_password,
)
from app.presentation.activity import router as activity_router
from app.presentation.auth import router as auth_router
from app.presentation.camera_dependencies import get_camera_service


class CameraServiceStub:
    cameras = [
        Camera(
            id=1,
            name="entrada",
            location="Principal",
            model="Demo",
            stream_url="https://stream.example.test/entrada/whep",
            status=CameraStatus.ONLINE,
        ),
        Camera(
            id=2,
            name="patio",
            location="Patio",
            model="Demo",
            stream_url="https://stream.example.test/patio/whep",
            status=CameraStatus.ONLINE,
        ),
    ]

    async def list_cameras(self):
        return self.cameras

    async def get_camera(self, camera_id: int):
        return next((camera for camera in self.cameras if camera.id == camera_id), None)


@dataclass
class ActivityHarness:
    client: TestClient
    session_factory: async_sessionmaker
    actor: dict[str, SimpleNamespace]

    def act_as(self, user_id: int, role: str) -> None:
        usernames = {1: "admin", 2: "supervisor", 3: "guardia"}
        self.actor["user"] = SimpleNamespace(
            id=user_id,
            username=usernames[user_id],
            role=role,
            is_active=True,
            is_admin=role == "admin",
        )

    def set_last_seen(self, session_id: str, last_seen_at: datetime) -> None:
        async def update_presence() -> None:
            async with self.session_factory() as session:
                presence = await session.get(UserPresenceSessionModel, session_id)
                assert presence is not None
                presence.last_seen_at = last_seen_at
                await session.commit()

        asyncio.run(update_presence())


@pytest.fixture
def activity_harness(tmp_path):
    """A real, isolated persistence layer behind just the activity router."""

    database_url = f"sqlite+aiosqlite:///{tmp_path / 'user_activity.db'}"
    engine = create_async_engine(database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def initialize_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            session.add_all(
                [
                    UserModel(
                        id=1,
                        username="admin",
                        password_hash="not-used-by-this-router",
                        is_active=True,
                        is_admin=True,
                        role="admin",
                    ),
                    UserModel(
                        id=2,
                        username="supervisor",
                        password_hash="not-used-by-this-router",
                        is_active=True,
                        is_admin=False,
                        role="supervisor",
                    ),
                    UserModel(
                        id=3,
                        username="guardia",
                        password_hash="not-used-by-this-router",
                        is_active=True,
                        is_admin=False,
                        role="guardia",
                    ),
                ]
            )
            session.add(UserCameraAccessModel(user_id=2, camera_name="entrada"))
            await session.commit()

    asyncio.run(initialize_database())

    app = FastAPI()
    app.include_router(activity_router, prefix="/api/v1")
    actor: dict[str, SimpleNamespace] = {
        "user": SimpleNamespace(
            id=1,
            username="admin",
            role="admin",
            is_active=True,
            is_admin=True,
        )
    }

    async def test_session():
        async with session_factory() as session:
            yield session

    def current_user():
        return actor["user"]

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_session] = test_session
    app.dependency_overrides[get_camera_service] = CameraServiceStub

    with TestClient(app) as client:
        yield ActivityHarness(client, session_factory, actor)

    asyncio.run(engine.dispose())


def user_presence(payload: dict, username: str) -> dict:
    return next(user for user in payload["users"] if user["username"] == username)


def parse_api_datetime(value: str) -> datetime:
    """SQLite can omit an offset even when the API column is UTC."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def test_authorized_camera_open_is_persisted_with_server_side_camera_details(
    activity_harness: ActivityHarness,
):
    activity_harness.act_as(2, "supervisor")
    before = datetime.now(timezone.utc)
    created = activity_harness.client.post("/api/v1/activity/cameras/1/opened")
    after = datetime.now(timezone.utc)

    assert created.status_code == 201
    event = created.json()
    assert event["user_id"] == 2
    assert event["username"] == "supervisor"
    assert event["user_role"] == "supervisor"
    assert event["event_type"] == "camera_opened"
    # The browser only submits an ID; the API obtains this trusted value from
    # the camera catalog so an audit record cannot spoof another camera name.
    assert event["camera_name"] == "entrada"
    assert before <= parse_api_datetime(event["occurred_at"]) <= after + timedelta(seconds=1)

    activity_harness.act_as(1, "admin")
    audit = activity_harness.client.get("/api/v1/admin/activity")

    assert audit.status_code == 200
    assert audit.json()["events"][0] == event


def test_camera_open_cannot_be_audited_for_a_camera_not_assigned_to_the_user(
    activity_harness: ActivityHarness,
):
    activity_harness.act_as(2, "supervisor")
    denied = activity_harness.client.post("/api/v1/activity/cameras/2/opened")

    assert denied.status_code == 404

    activity_harness.act_as(1, "admin")
    audit = activity_harness.client.get("/api/v1/admin/activity")
    assert audit.status_code == 200
    assert audit.json()["events"] == []


@pytest.mark.parametrize("role", ["supervisor", "guardia"])
def test_only_an_admin_can_read_other_users_activity(
    activity_harness: ActivityHarness, role: str
):
    user_id = 2 if role == "supervisor" else 3
    activity_harness.act_as(user_id, role)

    response = activity_harness.client.get("/api/v1/admin/activity")

    assert response.status_code == 403


def test_visible_heartbeat_marks_user_active_and_hidden_heartbeat_marks_them_inactive(
    activity_harness: ActivityHarness,
):
    session_id = "7634a1a5-925c-4a10-8fa3-fc9677ed32f8"
    activity_harness.act_as(2, "supervisor")

    visible = activity_harness.client.post(
        "/api/v1/activity/heartbeat",
        json={"session_id": session_id, "visible": True},
    )
    assert visible.status_code == 200
    assert visible.json() == {"ok": True}

    activity_harness.act_as(1, "admin")
    active_audit = activity_harness.client.get("/api/v1/admin/activity")
    presence = user_presence(active_audit.json(), "supervisor")
    assert set(presence) == {
        "id",
        "username",
        "role",
        "is_account_active",
        "active_now",
        "last_seen_at",
    }
    assert presence["id"] == 2
    assert presence["username"] == "supervisor"
    assert presence["role"] == "supervisor"
    assert presence["is_account_active"] is True
    assert presence["active_now"] is True
    assert presence["last_seen_at"] is not None
    assert parse_api_datetime(presence["last_seen_at"]) <= datetime.now(timezone.utc) + timedelta(seconds=1)

    activity_harness.act_as(2, "supervisor")
    hidden = activity_harness.client.post(
        "/api/v1/activity/heartbeat",
        json={"session_id": session_id, "visible": False},
    )
    assert hidden.status_code == 200

    activity_harness.act_as(1, "admin")
    inactive_audit = activity_harness.client.get("/api/v1/admin/activity")
    assert user_presence(inactive_audit.json(), "supervisor")["active_now"] is False


def test_stale_visible_heartbeat_is_not_treated_as_an_active_user(
    activity_harness: ActivityHarness,
):
    session_id = "ed44d2c4-68e1-4b56-a6d0-60d7ed75314a"
    activity_harness.act_as(2, "supervisor")
    created = activity_harness.client.post(
        "/api/v1/activity/heartbeat",
        json={"session_id": session_id, "visible": True},
    )
    assert created.status_code == 200

    # The public contract states a 45-second active window.  A last signal
    # outside it must not leave a user falsely marked "Activo ahora".
    activity_harness.set_last_seen(
        session_id, datetime.now(timezone.utc) - timedelta(seconds=46)
    )
    activity_harness.act_as(1, "admin")
    audit = activity_harness.client.get("/api/v1/admin/activity")

    assert audit.status_code == 200
    assert audit.json()["active_window_seconds"] == 45
    assert user_presence(audit.json(), "supervisor")["active_now"] is False


def test_a_presence_session_cannot_be_reused_by_another_user(
    activity_harness: ActivityHarness,
):
    session_id = "cbabbd13-08cd-4726-9a97-37dcebe9a7d3"
    activity_harness.act_as(2, "supervisor")
    first_heartbeat = activity_harness.client.post(
        "/api/v1/activity/heartbeat",
        json={"session_id": session_id, "visible": True},
    )
    assert first_heartbeat.status_code == 200

    activity_harness.act_as(3, "guardia")
    hijack_attempt = activity_harness.client.post(
        "/api/v1/activity/heartbeat",
        json={"session_id": session_id, "visible": True},
    )

    assert hijack_attempt.status_code == 403


def test_activity_models_are_populated_by_the_public_endpoints(
    activity_harness: ActivityHarness,
):
    """Smoke check that the persistence contract uses the expected models."""

    activity_harness.act_as(2, "supervisor")
    assert activity_harness.client.post("/api/v1/activity/cameras/1/opened").status_code == 201
    assert activity_harness.client.post(
        "/api/v1/activity/heartbeat",
        json={"session_id": "a9e02c55-87ea-4dc6-a9a2-714442a9824e", "visible": True},
    ).status_code == 200

    async def persisted_counts() -> tuple[int, int]:
        async with activity_harness.session_factory() as session:
            event_count = len((await session.scalars(select(UserActivityEventModel))).all())
            presence_count = len((await session.scalars(select(UserPresenceSessionModel))).all())
            return event_count, presence_count

    assert asyncio.run(persisted_counts()) == (1, 1)


def test_successful_login_creates_a_persistent_audit_event(tmp_path):
    """The log-in event is written by the real authentication route."""

    database_url = f"sqlite+aiosqlite:///{tmp_path / 'login_audit.db'}"
    engine = create_async_engine(database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def initialize_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            session.add(
                UserModel(
                    id=22,
                    username="operador",
                    password_hash=hash_password("secure-pass-1"),
                    is_active=True,
                    is_admin=False,
                    role="supervisor",
                )
            )
            await session.commit()

    asyncio.run(initialize_database())
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")

    async def test_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "operador", "password": "secure-pass-1"},
        )

    assert response.status_code == 200

    async def fetch_events() -> list[UserActivityEventModel]:
        async with session_factory() as session:
            return (await session.scalars(select(UserActivityEventModel))).all()

    events = asyncio.run(fetch_events())
    asyncio.run(engine.dispose())
    assert len(events) == 1
    assert events[0].user_id == 22
    assert events[0].event_type == "login"
    assert events[0].camera_name is None
