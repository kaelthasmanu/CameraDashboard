from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.camera import Camera, CameraStatus
from app.domain.recording import Recording
from app.infrastructure.db_models import UserCameraAccessModel, UserModel
from app.infrastructure.security import get_current_user, get_session, verify_password
from app.presentation import api as api_presentation
from app.presentation import users as users_presentation
from app.presentation.api import get_recording_service, router as api_router
from app.presentation.camera_dependencies import get_camera_service
from app.presentation.users import router as users_router


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

    async def get_camera(self, camera_id):
        return next((camera for camera in self.cameras if camera.id == camera_id), None)


class RecordingServiceStub:
    recordings = [
        Recording(
            id=1,
            camera_id=1,
            filename="entrada.mp4",
            path="/entrada.mp4",
            start_time=datetime(2026, 8, 16, tzinfo=timezone.utc),
            end_time=datetime(2026, 8, 16, 0, 1, tzinfo=timezone.utc),
            size_bytes=100,
            duration_seconds=60,
        ),
        Recording(
            id=2,
            camera_id=2,
            filename="patio.mp4",
            path="/patio.mp4",
            start_time=datetime(2026, 8, 16, tzinfo=timezone.utc),
            end_time=datetime(2026, 8, 16, 0, 1, tzinfo=timezone.utc),
            size_bytes=100,
            duration_seconds=60,
        ),
    ]

    async def search(self, camera_id=None, _day=None):
        if camera_id is None:
            return self.recordings
        return [recording for recording in self.recordings if recording.camera_id == camera_id]

    async def get(self, recording_id):
        return next((recording for recording in self.recordings if recording.id == recording_id), None)


def api_client_for(monkeypatch, role: str, camera_names: set[str] | None = None) -> TestClient:
    user = SimpleNamespace(id=10, role=role)

    async def authorized_camera_names(_user, _session):
        return None if role == "admin" else set(camera_names or ())

    monkeypatch.setattr(
        api_presentation, "get_authorized_camera_names", authorized_camera_names
    )
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = lambda: object()
    app.dependency_overrides[get_camera_service] = CameraServiceStub
    app.dependency_overrides[get_recording_service] = RecordingServiceStub
    return TestClient(app)


@pytest.mark.parametrize(
    ("role", "camera_names", "expected_ids"),
    [
        ("admin", {"entrada"}, [1, 2]),
        ("supervisor", {"entrada"}, [1]),
        ("guardia", {"patio"}, [2]),
        ("supervisor", set(), []),
        ("guardia", set(), []),
    ],
)
def test_camera_catalog_respects_each_users_assignment(
    monkeypatch, role, camera_names, expected_ids
):
    with api_client_for(monkeypatch, role, camera_names) as client:
        response = client.get("/api/v1/cameras")

    assert response.status_code == 200
    assert [camera["id"] for camera in response.json()] == expected_ids


def test_unassigned_camera_cannot_be_opened_directly(monkeypatch):
    with api_client_for(monkeypatch, "supervisor", {"entrada"}) as client:
        allowed = client.get("/api/v1/cameras/1")
        denied = client.get("/api/v1/cameras/2")

    assert allowed.status_code == 200
    assert denied.status_code == 404


@pytest.mark.parametrize(
    ("role", "camera_names", "expected_ids"),
    [
        ("admin", set(), [1, 2]),
        ("supervisor", {"entrada"}, [1]),
        ("supervisor", set(), []),
    ],
)
def test_recording_catalog_is_filtered_by_camera_assignment(
    monkeypatch, role, camera_names, expected_ids
):
    with api_client_for(monkeypatch, role, camera_names) as client:
        response = client.get("/api/v1/recordings")

    assert response.status_code == 200
    assert [recording["camera_id"] for recording in response.json()] == expected_ids


def test_supervisor_cannot_filter_or_open_an_unassigned_recording(monkeypatch):
    with api_client_for(monkeypatch, "supervisor", {"entrada"}) as client:
        filtered = client.get("/api/v1/recordings?camera_id=2")
        detail = client.get("/api/v1/recordings/2")
        stream = client.get("/api/v1/recordings/2/stream")

    assert filtered.status_code == 200
    assert filtered.json() == []
    assert detail.status_code == 404
    assert stream.status_code == 404


@pytest.mark.parametrize("path", ["/api/v1/recordings", "/api/v1/recordings/1", "/api/v1/recordings/1/stream"])
def test_guardia_cannot_access_recordings_even_when_a_camera_is_assigned(monkeypatch, path):
    with api_client_for(monkeypatch, "guardia", {"entrada"}) as client:
        response = client.get(path)

    assert response.status_code == 403


class ResultStub:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class UserSessionStub:
    def __init__(self, existing_user=None, users=None, assignments=None, target_user=None):
        self.existing_user = existing_user
        self.users = users or []
        self.assignments = assignments or []
        self.target_user = target_user
        self.created_user = None

    async def scalar(self, _query):
        return self.target_user or self.existing_user

    async def scalars(self, _query):
        return ResultStub(self.users)

    async def execute(self, query):
        if getattr(query, "is_delete", False):
            self.assignments = []
            return ResultStub([])
        return ResultStub(self.assignments)

    def add(self, user):
        self.created_user = user

    def add_all(self, assignments):
        self.assignments.extend(
            (assignment.user_id, assignment.camera_name) for assignment in assignments
        )

    async def flush(self):
        if self.created_user is not None:
            self.created_user.id = 99
            self.created_user.is_active = True

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def refresh(self, user):
        user.id = user.id or 99
        user.is_active = True


def users_client_for(role: str, session: UserSessionStub) -> TestClient:
    app = FastAPI()
    app.include_router(users_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role=role)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_camera_service] = CameraServiceStub
    return TestClient(app)


def test_admin_can_create_a_user_with_selected_cameras():
    session = UserSessionStub()
    with users_client_for("admin", session) as client:
        response = client.post(
            "/api/v1/users",
            json={
                "username": "maria.garcia",
                "password": "secure-pass-1",
                "role": "supervisor",
                "camera_names": ["entrada"],
            },
        )

    assert response.status_code == 201
    assert response.json() == {
        "id": 99,
        "username": "maria.garcia",
        "is_active": True,
        "is_admin": False,
        "role": "supervisor",
        "camera_names": ["entrada"],
    }
    assert session.created_user is not None
    assert verify_password("secure-pass-1", session.created_user.password_hash)
    assert session.assignments == [(99, "entrada")]


def test_admin_can_create_a_non_admin_without_cameras():
    session = UserSessionStub()
    with users_client_for("admin", session) as client:
        response = client.post(
            "/api/v1/users",
            json={"username": "guardia", "password": "secure-pass-1", "role": "guardia"},
        )

    assert response.status_code == 201
    assert response.json()["camera_names"] == []
    assert session.assignments == []


def test_unknown_camera_is_rejected_without_creating_a_user():
    session = UserSessionStub()
    with users_client_for("admin", session) as client:
        response = client.post(
            "/api/v1/users",
            json={
                "username": "guardia",
                "password": "secure-pass-1",
                "role": "guardia",
                "camera_names": ["desconocida"],
            },
        )

    assert response.status_code == 422
    assert session.created_user is None


@pytest.mark.parametrize("role", ["supervisor", "guardia"])
def test_non_admin_cannot_create_users(role):
    session = UserSessionStub()
    with users_client_for(role, session) as client:
        response = client.post(
            "/api/v1/users",
            json={"username": "nuevo_usuario", "password": "secure-pass-1", "role": "guardia"},
        )

    assert response.status_code == 403
    assert session.created_user is None


def test_admin_can_list_users_with_their_camera_assignments():
    admin = UserModel(id=1, username="admin", password_hash="not-exposed", is_active=True, is_admin=True, role="admin")
    supervisor = UserModel(id=2, username="supervisor", password_hash="not-exposed", is_active=True, is_admin=False, role="supervisor")
    session = UserSessionStub(users=[admin, supervisor], assignments=[(2, "entrada")])
    with users_client_for("admin", session) as client:
        response = client.get("/api/v1/users")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "username": "admin", "is_active": True, "is_admin": True, "role": "admin", "camera_names": []},
        {"id": 2, "username": "supervisor", "is_active": True, "is_admin": False, "role": "supervisor", "camera_names": ["entrada"]},
    ]


def test_admin_can_replace_a_users_camera_assignments():
    supervisor = UserModel(id=2, username="supervisor", password_hash="not-exposed", is_active=True, is_admin=False, role="supervisor")
    session = UserSessionStub(target_user=supervisor, assignments=[(2, "entrada"), (2, "patio")])
    with users_client_for("admin", session) as client:
        response = client.put("/api/v1/users/2/cameras", json={"camera_names": ["patio"]})

    assert response.status_code == 200
    assert response.json()["camera_names"] == ["patio"]
    assert session.assignments == [(2, "patio")]


@pytest.mark.parametrize("role", ["supervisor", "guardia"])
def test_non_admin_cannot_change_a_users_camera_assignments(role):
    supervisor = UserModel(id=2, username="supervisor", password_hash="not-exposed", is_active=True, is_admin=False, role="supervisor")
    session = UserSessionStub(target_user=supervisor, assignments=[(2, "entrada")])
    with users_client_for(role, session) as client:
        response = client.put("/api/v1/users/2/cameras", json={"camera_names": []})

    assert response.status_code == 403
    assert session.assignments == [(2, "entrada")]
