"""User activity audit and browser-presence endpoints.

The dashboard receives a heartbeat from every visible browser tab.  A user is
considered active only while at least one of those server-timestamped signals
is recent; this avoids an unreliable permanent ``online`` flag when a browser
is closed or loses connectivity without a logout request.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..application.camera_service import CameraService
from ..infrastructure.db_models import (
    UserActivityEventModel,
    UserModel,
    UserPresenceSessionModel,
)
from ..infrastructure.security import (
    get_authorized_camera_names,
    get_session,
    require_admin,
    require_live_access,
)
from .camera_dependencies import get_camera_service
from .schemas import (
    ActivityEventResponse,
    AdminActivityResponse,
    PresenceHeartbeatRequest,
    UserPresenceResponse,
)


router = APIRouter(tags=["activity"])

# The browser sends a heartbeat every 15 seconds.  Three missed intervals are
# enough to mark the session inactive, while avoiding false negatives from a
# single delayed request.
ACTIVE_WINDOW_SECONDS = 45


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Normalize SQLite's occasionally naive datetimes to UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def add_activity_event(
    session: AsyncSession,
    *,
    user_id: int,
    event_type: str,
    camera_name: str | None = None,
) -> UserActivityEventModel:
    """Append a server-timestamped audit event to the current transaction."""

    event = UserActivityEventModel(
        user_id=user_id,
        event_type=event_type,
        camera_name=camera_name,
        occurred_at=utc_now(),
    )
    session.add(event)
    return event


def serialize_activity_event(
    event: UserActivityEventModel, username: str, role: str
) -> ActivityEventResponse:
    return ActivityEventResponse(
        id=event.id,
        user_id=event.user_id,
        username=username,
        user_role=role,
        event_type=event.event_type,
        camera_name=event.camera_name,
        occurred_at=as_utc(event.occurred_at),
    )


@router.post("/activity/heartbeat")
async def heartbeat(
    payload: PresenceHeartbeatRequest,
    user: UserModel = Depends(require_live_access),
    session: AsyncSession = Depends(get_session),
):
    """Record one browser tab's currently visible state using server time."""

    presence = await session.get(UserPresenceSessionModel, payload.session_id)
    if presence is not None and presence.user_id != user.id:
        # A generated tab ID must not be re-used to update another user's
        # presence, even if it somehow leaks between browsers.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La sesión de presencia pertenece a otro usuario",
        )

    now = utc_now()
    if presence is None:
        session.add(
            UserPresenceSessionModel(
                session_id=payload.session_id,
                user_id=user.id,
                last_seen_at=now,
                is_visible=payload.visible,
            )
        )
    else:
        presence.last_seen_at = now
        presence.is_visible = payload.visible

    try:
        await session.commit()
    except IntegrityError:
        # Two initial heartbeats from the same tab can overlap (for example in
        # React development mode).  Re-read the row after the competing insert
        # commits and turn it into the normal update instead of losing presence.
        await session.rollback()
        presence = await session.get(UserPresenceSessionModel, payload.session_id)
        if presence is None:
            raise
        if presence.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="La sesión de presencia pertenece a otro usuario",
            )
        presence.last_seen_at = now
        presence.is_visible = payload.visible
        await session.commit()
    return {"ok": True}


@router.post(
    "/activity/cameras/{camera_id}/opened",
    response_model=ActivityEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def camera_opened(
    camera_id: int,
    service: CameraService = Depends(get_camera_service),
    user: UserModel = Depends(require_live_access),
    session: AsyncSession = Depends(get_session),
):
    """Audit an intentional camera opening after enforcing current access."""

    camera = await service.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    camera_names = await get_authorized_camera_names(user, session)
    if camera_names is not None and camera.name not in camera_names:
        # Return 404 so an unassigned camera is not disclosed through the log.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    event = add_activity_event(
        session,
        user_id=user.id,
        event_type="camera_opened",
        camera_name=camera.name,
    )
    await session.commit()
    await session.refresh(event)
    return serialize_activity_event(event, user.username, user.role)


@router.get("/admin/activity", response_model=AdminActivityResponse)
async def admin_activity(
    limit: int = Query(default=100, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _: UserModel = Depends(require_admin),
):
    """Return the latest auditable actions and the derived current presence.

    ``active_now`` means that a visible tab supplied a heartbeat within the
    last ``active_window_seconds``.  ``last_seen_at`` is always server time so
    an administrator can independently judge the state near the boundary.
    """

    users = (await session.scalars(select(UserModel).order_by(UserModel.username))).all()
    user_by_id = {user.id: user for user in users}
    now = utc_now()
    cutoff = now - timedelta(seconds=ACTIVE_WINDOW_SECONDS)

    presence_rows = (
        await session.scalars(select(UserPresenceSessionModel))
    ).all()
    latest_seen_by_user: dict[int, datetime] = {}
    active_user_ids: set[int] = set()
    for presence in presence_rows:
        last_seen_at = as_utc(presence.last_seen_at)
        previous_seen_at = latest_seen_by_user.get(presence.user_id)
        if previous_seen_at is None or last_seen_at > previous_seen_at:
            latest_seen_by_user[presence.user_id] = last_seen_at
        if presence.is_visible and last_seen_at >= cutoff:
            active_user_ids.add(presence.user_id)

    event_rows = (
        await session.execute(
            select(UserActivityEventModel, UserModel.username, UserModel.role)
            .join(UserModel, UserActivityEventModel.user_id == UserModel.id)
            .order_by(UserActivityEventModel.occurred_at.desc(), UserActivityEventModel.id.desc())
            .limit(limit)
        )
    ).all()

    return AdminActivityResponse(
        events=[
            serialize_activity_event(event, username, role)
            for event, username, role in event_rows
        ],
        users=[
            UserPresenceResponse(
                id=user.id,
                username=user.username,
                role=user.role,
                is_account_active=user.is_active,
                # An account disabled after its last heartbeat must never be
                # presented as currently active, even during the short TTL.
                active_now=user.is_active and user.id in active_user_ids,
                last_seen_at=latest_seen_by_user.get(user.id),
            )
            for user in user_by_id.values()
        ],
        active_window_seconds=ACTIVE_WINDOW_SECONDS,
    )
