from enum import StrEnum


class UserRole(StrEnum):
    """Roles supported by the camera dashboard."""

    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    GUARDIA = "guardia"
