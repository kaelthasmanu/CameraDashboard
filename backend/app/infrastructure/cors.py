"""Strict, environment-driven CORS configuration helpers.

Browsers send one concrete ``Origin`` value, never a CIDR.  Exact origins are
therefore the preferred allow-list.  CIDRs are an opt-in convenience for
trusted internal networks and are matched only against literal IP hosts,
specific schemes and specific ports.
"""

from collections.abc import Sequence
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from urllib.parse import urlsplit

from starlette.middleware.cors import CORSMiddleware


OriginNetwork = IPv4Network | IPv6Network
SUPPORTED_SCHEMES = frozenset({"http", "https"})
DEFAULT_PORTS = {"http": 80, "https": 443}


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _invalid_setting(setting: str, value: str, reason: str) -> ValueError:
    return ValueError(f"{setting} contiene un valor no válido ({value!r}): {reason}")


def _normalize_origin(origin: str) -> str:
    try:
        parsed = urlsplit(origin)
        port = parsed.port
    except ValueError as error:
        raise _invalid_setting("CORS_ORIGINS", origin, "puerto inválido") from error

    if parsed.scheme.lower() not in SUPPORTED_SCHEMES:
        raise _invalid_setting("CORS_ORIGINS", origin, "usa http:// o https://")
    if not parsed.hostname or parsed.username or parsed.password:
        raise _invalid_setting("CORS_ORIGINS", origin, "debe incluir únicamente host y puerto")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise _invalid_setting("CORS_ORIGINS", origin, "no debe incluir ruta, query ni fragmento")

    try:
        hostname = parsed.hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise _invalid_setting("CORS_ORIGINS", origin, "host inválido") from error

    host = f"[{hostname}]" if ":" in hostname else hostname
    scheme = parsed.scheme.lower()
    if port is None or port == DEFAULT_PORTS[scheme]:
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


def parse_cors_origins(value: str) -> list[str]:
    """Parse exact browser origins from ``CORS_ORIGINS``.

    Wildcards are deliberately rejected because this application uses
    credentialed requests.  List every trusted dashboard origin instead.
    """

    origins = split_csv(value)
    if "*" in origins:
        raise ValueError(
            "CORS_ORIGINS no permite '*' cuando se usan credenciales; "
            "declara cada origen explícitamente"
        )
    return list(dict.fromkeys(_normalize_origin(origin) for origin in origins))


def parse_cors_origin_cidrs(value: str) -> list[OriginNetwork]:
    """Parse the optional IP networks from ``CORS_ORIGIN_CIDRS``."""

    networks: list[OriginNetwork] = []
    for cidr in split_csv(value):
        try:
            networks.append(ip_network(cidr, strict=True))
        except ValueError as error:
            raise _invalid_setting("CORS_ORIGIN_CIDRS", cidr, "CIDR inválido") from error
    return networks


def parse_cors_origin_cidr_ports(value: str) -> list[int]:
    ports: list[int] = []
    for raw_port in split_csv(value):
        try:
            port = int(raw_port)
        except ValueError as error:
            raise _invalid_setting(
                "CORS_ORIGIN_CIDR_PORTS", raw_port, "puerto inválido"
            ) from error
        if not 1 <= port <= 65535:
            raise _invalid_setting(
                "CORS_ORIGIN_CIDR_PORTS", raw_port, "debe estar entre 1 y 65535"
            )
        ports.append(port)
    return list(dict.fromkeys(ports))


class CIDRCORSMiddleware(CORSMiddleware):
    """Starlette CORS with a fail-closed optional CIDR origin allow-list."""

    def __init__(
        self,
        app,
        *,
        allow_origin_cidrs: Sequence[OriginNetwork] = (),
        cidr_allowed_ports: Sequence[int] = (),
        **kwargs,
    ):
        self.allow_origin_cidrs = tuple(allow_origin_cidrs)
        self.cidr_allowed_ports = frozenset(cidr_allowed_ports)
        super().__init__(app, **kwargs)

    def is_allowed_origin(self, origin: str) -> bool:
        if super().is_allowed_origin(origin):
            return True
        if not self.allow_origin_cidrs or not self.cidr_allowed_ports:
            return False

        try:
            parsed = urlsplit(origin)
            port = parsed.port
        except ValueError:
            return False

        scheme = parsed.scheme.lower()
        if (
            scheme not in SUPPORTED_SCHEMES
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            return False

        effective_port = port if port is not None else DEFAULT_PORTS.get(scheme)
        if effective_port not in self.cidr_allowed_ports:
            return False

        try:
            host = ip_address(parsed.hostname)
        except ValueError:
            # CIDRs never match DNS names. Add names to CORS_ORIGINS instead.
            return False
        return any(host in network for network in self.allow_origin_cidrs)
