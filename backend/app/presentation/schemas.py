from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator
from ..domain.camera import CameraStatus
from ..domain.user import UserRole

class CameraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    location: str
    model: str
    stream_url: str
    preview_url: str | None = None
    status: CameraStatus
    enabled: bool
    last_seen: datetime | None

class HealthResponse(BaseModel):
    status: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    username: str
    is_active: bool
    is_admin: bool
    role: UserRole
    camera_names: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    camera_names: list[str] = Field(default_factory=list)

    @field_validator("username")
    @classmethod
    def validate_username(cls, username: str) -> str:
        normalized = username.strip()
        if len(normalized) < 3:
            raise ValueError("El usuario debe tener al menos 3 caracteres")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", normalized):
            raise ValueError("El usuario solo puede incluir letras, números, puntos, guiones y guiones bajos")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, password: str) -> str:
        if not password.strip():
            raise ValueError("La contraseña no puede estar vacía")
        return password

    @field_validator("camera_names")
    @classmethod
    def validate_camera_names(cls, camera_names: list[str]) -> list[str]:
        normalized = [camera_name.strip() for camera_name in camera_names]
        if any(not camera_name for camera_name in normalized):
            raise ValueError("Los nombres de cámara no pueden estar vacíos")
        return list(dict.fromkeys(normalized))


class UpdateUserCameraAccessRequest(BaseModel):
    camera_names: list[str] = Field(default_factory=list)

    @field_validator("camera_names")
    @classmethod
    def validate_camera_names(cls, camera_names: list[str]) -> list[str]:
        normalized = [camera_name.strip() for camera_name in camera_names]
        if any(not camera_name for camera_name in normalized):
            raise ValueError("Los nombres de cámara no pueden estar vacíos")
        return list(dict.fromkeys(normalized))


class PresenceHeartbeatRequest(BaseModel):
    """State reported by one browser tab, timestamped by the server."""

    session_id: str = Field(min_length=16, max_length=128)
    visible: bool

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, session_id: str) -> str:
        normalized = session_id.strip()
        if not re.fullmatch(r"[A-Za-z0-9-]{16,128}", normalized):
            raise ValueError("El identificador de sesión no tiene un formato válido")
        return normalized


class ActivityEventResponse(BaseModel):
    id: int
    user_id: int
    username: str
    user_role: UserRole
    event_type: str
    camera_name: str | None = None
    occurred_at: datetime


class UserPresenceResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    is_account_active: bool
    active_now: bool
    last_seen_at: datetime | None = None


class AdminActivityResponse(BaseModel):
    events: list[ActivityEventResponse]
    users: list[UserPresenceResponse]
    active_window_seconds: int

class RecordingResponse(BaseModel):
    id: int
    camera_id: int
    filename: str
    start_time: datetime
    end_time: datetime
    size_bytes: int
    duration_seconds: int
