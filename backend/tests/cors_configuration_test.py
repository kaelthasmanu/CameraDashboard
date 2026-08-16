"""Focused CORS regression coverage.

The dashboard can be hosted on a named origin, a single LAN address, or a
trusted LAN subnet.  The security boundary must stay fail-closed: a browser
origin that is not explicitly configured (or whose *IP literal* is outside a
configured CIDR) must not receive CORS permission.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.infrastructure.cors import (
    CIDRCORSMiddleware,
    parse_cors_origin_cidr_ports,
    parse_cors_origin_cidrs,
    parse_cors_origins,
)


def cors_test_app(
    *,
    origins: list[str],
    cidrs: list[object] | None = None,
    cidr_ports: list[int] | None = None,
) -> FastAPI:
    """Build a small application so middleware behavior is tested in isolation."""

    app = FastAPI()
    app.add_middleware(
        CIDRCORSMiddleware,
        allow_origins=origins,
        allow_origin_cidrs=cidrs or [],
        cidr_allowed_ports=cidr_ports or [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/probe")
    async def probe():
        return {"ok": True}

    return app


def test_exact_origins_from_the_environment_list_are_trimmed_and_allowed():
    origins = parse_cors_origins(
        " https://dashboard.example.test , http://10.34.8.174:5173 "
    )
    app = cors_test_app(origins=origins)

    with TestClient(app) as client:
        named_origin = client.get(
            "/probe", headers={"Origin": "https://dashboard.example.test"}
        )
        ip_origin = client.get(
            "/probe", headers={"Origin": "http://10.34.8.174:5173"}
        )

    assert named_origin.status_code == 200
    assert named_origin.headers["access-control-allow-origin"] == (
        "https://dashboard.example.test"
    )
    assert named_origin.headers["access-control-allow-credentials"] == "true"
    assert ip_origin.headers["access-control-allow-origin"] == (
        "http://10.34.8.174:5173"
    )


def test_unlisted_origin_receives_no_cors_permission():
    app = cors_test_app(origins=parse_cors_origins("https://dashboard.example.test"))

    with TestClient(app) as client:
        response = client.get("/probe", headers={"Origin": "https://evil.example.test"})

    # The route itself can answer, but a browser must not be given permission
    # to read that answer from a non-configured origin.
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cidr_allows_ip_literal_preflight_with_credentials():
    app = cors_test_app(
        origins=parse_cors_origins("https://dashboard.example.test"),
        cidrs=parse_cors_origin_cidrs("10.34.8.0/24"),
        cidr_ports=parse_cors_origin_cidr_ports("5173"),
    )
    origin = "http://10.34.8.174:5173"

    with TestClient(app) as client:
        response = client.options(
            "/probe",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "GET" in response.headers["access-control-allow-methods"]
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers


def test_cidr_does_not_allow_an_unconfigured_browser_port():
    app = cors_test_app(
        origins=[],
        cidrs=parse_cors_origin_cidrs("10.34.8.0/24"),
        cidr_ports=parse_cors_origin_cidr_ports("5173"),
    )

    with TestClient(app) as client:
        response = client.options(
            "/probe",
            headers={
                "Origin": "http://10.34.8.174:8888",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cidr_never_treats_a_hostname_as_an_ip_address():
    app = cors_test_app(
        origins=[],
        cidrs=parse_cors_origin_cidrs("10.34.8.0/24"),
        cidr_ports=parse_cors_origin_cidr_ports("5173"),
    )

    with TestClient(app) as client:
        outside_ip = client.get("/probe", headers={"Origin": "http://10.34.9.10:5173"})
        hostname = client.get(
            "/probe", headers={"Origin": "http://10.34.8.174.evil.example:5173"}
        )

    assert "access-control-allow-origin" not in outside_ip.headers
    assert "access-control-allow-origin" not in hostname.headers


@pytest.mark.parametrize(
    "raw_value",
    [
        "10.34.8.0/99",
        "10.34.8.0/not-a-prefix",
        "not-a-network",
    ],
)
def test_invalid_cidr_configuration_is_rejected_fail_closed(raw_value: str):
    with pytest.raises(ValueError):
        parse_cors_origin_cidrs(raw_value)


@pytest.mark.parametrize("raw_value", ["0", "65536", "not-a-port"])
def test_invalid_cidr_port_configuration_is_rejected_fail_closed(raw_value: str):
    with pytest.raises(ValueError):
        parse_cors_origin_cidr_ports(raw_value)


@pytest.mark.parametrize(
    "raw_value",
    [
        "dashboard.example.test",
        "ftp://dashboard.example.test",
        "https://dashboard.example.test/not-an-origin",
    ],
)
def test_invalid_exact_origin_configuration_is_rejected_fail_closed(raw_value: str):
    with pytest.raises(ValueError):
        parse_cors_origins(raw_value)
