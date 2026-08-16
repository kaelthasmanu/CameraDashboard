from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
from ..domain.user import UserRole

class CameraModel(Base):
    __tablename__ = "cameras"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(180))
    model: Mapped[str] = mapped_column(String(120))
    stream_url: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class RecordingModel(Base):
    __tablename__ = "recordings"
    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(1000), unique=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    size_bytes: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[int] = mapped_column(Integer)

class UserModel(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # is_admin is kept while existing installations migrate. New authorization
    # decisions must use role, which is the source of truth.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[str] = mapped_column(
        String(20), default=UserRole.GUARDIA.value, server_default=UserRole.GUARDIA.value
    )


class UserCameraAccessModel(Base):
    """MediaMTX camera paths a non-admin user is allowed to access.

    Cameras are sourced dynamically from MediaMTX. Its numeric IDs depend on
    the YAML order, so a stable path name is stored instead of camera_id.
    The user foreign key still ensures access rows are removed with their user.
    """

    __tablename__ = "user_camera_access"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    camera_name: Mapped[str] = mapped_column(String(120), primary_key=True)


class UserActivityEventModel(Base):
    """An append-only audit record for meaningful actions in the dashboard."""

    __tablename__ = "user_activity_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    # Keep the MediaMTX path, which remains stable if the YAML camera order changes.
    camera_name: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class UserPresenceSessionModel(Base):
    """The most recent server-observed state for one browser tab session.

    Presence is intentionally derived from ``last_seen_at`` instead of a
    persistent online flag: a browser or network can disappear without sending
    a final request.
    """

    __tablename__ = "user_presence_sessions"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=False)
