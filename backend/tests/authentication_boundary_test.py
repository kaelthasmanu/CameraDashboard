"""Regression coverage for the backend's unauthenticated request boundary.

Only the health check and the credential-submission route are intentionally
public.  Every other application route must reject a request that has neither
a Bearer token nor the authenticated session cookie.  Keeping this list in one
place makes a newly added endpoint an explicit security decision during code
review.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

from app.infrastructure.security import get_session
from app.main import app


# Each tuple contains the HTTP method, an example concrete path, and any body
# needed to ensure request-body validation cannot obscure an authentication
# failure.  The list mirrors every non-public route mounted by ``app.main``.
PROTECTED_REQUESTS: list[tuple[str, str, dict[str, Any]]] = [
    ("get", "/api/v1/cameras", {}),
    ("get", "/api/v1/cameras/1", {}),
    ("get", "/api/v1/recordings", {}),
    ("get", "/api/v1/recordings/1", {}),
    ("get", "/api/v1/recordings/1/stream", {}),
    ("post", "/api/v1/auth/logout", {}),
    ("get", "/api/v1/auth/me", {}),
    (
        "post",
        "/api/v1/activity/heartbeat",
        {"json": {"session_id": "c6a1a1f4-9df8-482f-8a2d-7d72a67ec5c5", "visible": True}},
    ),
    ("post", "/api/v1/activity/cameras/1/opened", {}),
    ("get", "/api/v1/admin/activity", {}),
    ("get", "/api/v1/users", {}),
    (
        "post",
        "/api/v1/users",
        {
            "json": {
                "username": "usuario-prueba",
                "password": "secure-pass-1",
                "role": "guardia",
            }
        },
    ),
    ("put", "/api/v1/users/1/cameras", {"json": {"camera_names": []}}),
    # API metadata can reveal routes and schemas, so it follows the same
    # authentication boundary as the application endpoints.
    ("get", "/openapi.json", {}),
    ("get", "/docs", {}),
    ("get", "/redoc", {}),
]

PUBLIC_ROUTE_METHODS = {
    ("get", "/health"),
    ("post", "/api/v1/auth/login"),
}

PROTECTED_ROUTE_METHODS = {
    ("get", "/api/v1/cameras"),
    ("get", "/api/v1/cameras/{camera_id}"),
    ("get", "/api/v1/recordings"),
    ("get", "/api/v1/recordings/{recording_id}"),
    ("get", "/api/v1/recordings/{recording_id}/stream"),
    ("post", "/api/v1/auth/logout"),
    ("get", "/api/v1/auth/me"),
    ("post", "/api/v1/activity/heartbeat"),
    ("post", "/api/v1/activity/cameras/{camera_id}/opened"),
    ("get", "/api/v1/admin/activity"),
    ("get", "/api/v1/users"),
    ("post", "/api/v1/users"),
    ("put", "/api/v1/users/{user_id}/cameras"),
    ("get", "/openapi.json"),
    ("get", "/docs"),
    ("get", "/redoc"),
}


@pytest.fixture
def unauthenticated_client() -> Iterator[TestClient]:
    """Use the real route registration without running database startup hooks."""

    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client
    finally:
        client.close()


@pytest.mark.parametrize(("method", "path", "request_options"), PROTECTED_REQUESTS)
def test_every_protected_route_rejects_an_unauthenticated_request(
    unauthenticated_client: TestClient,
    method: str,
    path: str,
    request_options: dict[str, Any],
):
    response = getattr(unauthenticated_client, method)(path, **request_options)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_health_remains_public_for_container_and_load_balancer_checks(
    unauthenticated_client: TestClient,
):
    response = unauthenticated_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_remains_public_and_reaches_credential_validation(
    unauthenticated_client: TestClient,
):
    """A missing Bearer token must not block credential submission itself."""

    class UnknownUserSession:
        async def scalar(self, _query):
            return None

    async def unknown_user_session():
        yield UnknownUserSession()

    app.dependency_overrides[get_session] = unknown_user_session
    try:
        response = unauthenticated_client.post(
            "/api/v1/auth/login",
            data={"username": "desconocido", "password": "secure-pass-1"},
        )
    finally:
        app.dependency_overrides.pop(get_session, None)

    # This 401 is deliberately the login endpoint's credential response, not
    # the generic missing-token response used by protected routes above.
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}


def test_route_registry_has_an_explicit_authentication_decision_for_every_route():
    """Prevent a newly mounted route from quietly escaping the test matrix."""

    registered_route_methods = {
        (method.lower(), route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    expected_route_methods = PROTECTED_ROUTE_METHODS | PUBLIC_ROUTE_METHODS

    assert registered_route_methods == expected_route_methods
