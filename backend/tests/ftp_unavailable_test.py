import asyncio
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.infrastructure.recording_repository import (
    FtpRecordingRepository,
    FtpRecordingUnavailableError,
)
from app.infrastructure import recording_repository
from app.infrastructure.security import get_current_user
from app.presentation.api import get_recording_service, router


class ListingTimeoutFTP:
    def __init__(self):
        self.quit_called = False

    def mlsd(self, *_args, **_kwargs):
        raise TimeoutError("timed out")

    def quit(self):
        self.quit_called = True


class UnavailableRecordingService:
    async def search(self, *_args, **_kwargs):
        raise FtpRecordingUnavailableError("directory listing")


def test_ftp_repository_wraps_listing_timeout_and_closes_connection(monkeypatch):
    repository = FtpRecordingRepository()
    ftp = ListingTimeoutFTP()
    monkeypatch.setattr(repository, "_connect", lambda: ftp)

    with pytest.raises(FtpRecordingUnavailableError) as error:
        asyncio.run(repository.search())

    assert error.value.operation == "directory listing"
    assert ftp.quit_called


def test_ftp_repository_wraps_connection_oserror(monkeypatch):
    repository = FtpRecordingRepository()

    def raise_oserror(*_args, **_kwargs):
        raise OSError("network unreachable")

    monkeypatch.setattr(recording_repository.FTP, "connect", raise_oserror)

    with pytest.raises(FtpRecordingUnavailableError) as error:
        repository._connect()

    assert error.value.operation == "connection"


def test_recordings_endpoint_returns_safe_503_when_ftp_is_unavailable():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role="admin")
    app.dependency_overrides[get_recording_service] = UnavailableRecordingService

    with TestClient(app) as client:
        response = client.get("/api/v1/recordings?day=2026-08-15")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "El catálogo de grabaciones no está disponible temporalmente."
    }
    assert response.headers["retry-after"] == "30"
