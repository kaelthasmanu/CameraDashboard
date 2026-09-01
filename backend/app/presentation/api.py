from datetime import date
import asyncio
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from ..application.camera_service import CameraService
from .camera_dependencies import get_camera_service, get_person_recognition_service
from .schemas import CameraResponse
from ..application.recording_service import RecordingService
from ..infrastructure.recording_repository import (
    FtpRecordingRepository,
    FtpRecordingUnavailableError,
)
from .schemas import RecordingResponse
from ..infrastructure.storage import FileStorage, StorageError
from ..infrastructure.security import (
    get_authorized_camera_names,
    get_session,
    require_live_access,
    require_recording_access,
)
from ..infrastructure.db_models import UserModel
from ..infrastructure.db_models import UserCameraAlarmPreferenceModel
from ..infrastructure.database import SessionLocal
from .schemas import CameraResponse, PersonDetectionResponse, UpdateAlarmPreferenceRequest
from ..infrastructure.person_detection import PersonRecognitionService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..infrastructure.settings import settings

router = APIRouter()
recording_repository = FtpRecordingRepository()
storage = FileStorage()

def get_recording_service() -> RecordingService:
    return RecordingService(recording_repository)


async def get_visible_camera_ids(
    user: UserModel,
    session: AsyncSession,
    camera_service: CameraService,
) -> set[int] | None:
    camera_names = await get_authorized_camera_names(user, session)
    if camera_names is None:
        return None
    cameras = await camera_service.list_cameras()
    return {camera.id for camera in cameras if camera.name in camera_names}

async def get_authorized_camera(
    camera_id: int,
    user: UserModel,
    session: AsyncSession,
    camera_service: CameraService,
):
    camera = await camera_service.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    camera_names = await get_authorized_camera_names(user, session)
    if camera_names is not None and camera.name not in camera_names:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.get("/person-detections", response_model=list[PersonDetectionResponse])
async def list_person_detections(
    user: UserModel = Depends(require_live_access),
    session: AsyncSession = Depends(get_session),
    camera_service: CameraService = Depends(get_camera_service),
    recognition_service: PersonRecognitionService = Depends(get_person_recognition_service),
):
    camera_ids = await get_visible_camera_ids(user, session, camera_service)
    return recognition_service.detections_for(camera_ids)


@router.websocket("/person-detections/ws")
async def person_detections_websocket(websocket: WebSocket):
    token = websocket.query_params.get("token") or websocket.cookies.get("access_token")
    if not token:
        await websocket.close(code=4401)
        return
    try:
        user_id = int(jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]).get("sub", ""))
    except (jwt.InvalidTokenError, ValueError, TypeError):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    recognition_service = get_person_recognition_service()
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    async with SessionLocal() as session:
        user = await session.scalar(select(UserModel).where(UserModel.id == user_id, UserModel.is_active.is_(True)))
        if user is None:
            await websocket.close(code=4401)
            return
        camera_ids = await get_visible_camera_ids(user, session, get_camera_service())

        def publish(event: dict[str, object]) -> None:
            event_camera_id = event.get("camera_id")
            if camera_ids is not None and event_camera_id not in camera_ids:
                return
            loop.call_soon_threadsafe(queue.put_nowait, event)

        recognition_service.subscribe(publish)
        try:
            for detection in recognition_service.detections_for(camera_ids):
                await websocket.send_json({
                    "type": "person_detection",
                    "camera_id": detection.camera_id,
                    "person_count": detection.person_count,
                    "detected_at": detection.detected_at.isoformat(),
                })
            while True:
                await websocket.send_json(await queue.get())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            recognition_service.unsubscribe(publish)

@router.get("/alarm-preferences", response_model=dict[str, bool])
async def list_alarm_preferences(
    user: UserModel = Depends(require_live_access),
    session: AsyncSession = Depends(get_session),
    camera_service: CameraService = Depends(get_camera_service),
):
    cameras = await camera_service.list_cameras()
    camera_names = await get_authorized_camera_names(user, session)
    visible_names = {
        camera.name for camera in cameras
        if camera_names is None or camera.name in camera_names
    }
    rows = (
        await session.scalars(
            select(UserCameraAlarmPreferenceModel).where(
                UserCameraAlarmPreferenceModel.user_id == user.id,
                UserCameraAlarmPreferenceModel.camera_name.in_(visible_names),
            )
        )
    ).all()
    preferences = {camera_name: True for camera_name in visible_names}
    preferences.update({row.camera_name: row.enabled for row in rows})
    return preferences

@router.put("/alarm-preferences/{camera_id}", response_model=dict[str, bool])
async def update_alarm_preference(
    camera_id: int,
    payload: UpdateAlarmPreferenceRequest,
    user: UserModel = Depends(require_live_access),
    session: AsyncSession = Depends(get_session),
    camera_service: CameraService = Depends(get_camera_service),
):
    camera = await get_authorized_camera(camera_id, user, session, camera_service)
    preference = await session.scalar(
        select(UserCameraAlarmPreferenceModel).where(
            UserCameraAlarmPreferenceModel.user_id == user.id,
            UserCameraAlarmPreferenceModel.camera_name == camera.name,
        )
    )
    if preference is None:
        preference = UserCameraAlarmPreferenceModel(
            user_id=user.id, camera_name=camera.name, enabled=payload.enabled
        )
        session.add(preference)
    else:
        preference.enabled = payload.enabled
    await session.commit()
    return {camera.name: payload.enabled}

@router.get("/cameras", response_model=list[CameraResponse])
async def list_cameras(
    service: CameraService = Depends(get_camera_service),
    user: UserModel = Depends(require_live_access),
    session: AsyncSession = Depends(get_session),
):
    cameras = await service.list_cameras()
    camera_names = await get_authorized_camera_names(user, session)
    if camera_names is None:
        return cameras
    return [camera for camera in cameras if camera.name in camera_names]

@router.get("/cameras/{camera_id}", response_model=CameraResponse)
async def get_camera(
    camera_id: int,
    service: CameraService = Depends(get_camera_service),
    user: UserModel = Depends(require_live_access),
    session: AsyncSession = Depends(get_session),
):
    camera = await service.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    camera_names = await get_authorized_camera_names(user, session)
    if camera_names is not None and camera.name not in camera_names:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera

@router.get("/recordings", response_model=list[RecordingResponse])
async def list_recordings(
    camera_id: int | None = None,
    day: date | None = None,
    service: RecordingService = Depends(get_recording_service),
    user: UserModel = Depends(require_recording_access),
    session: AsyncSession = Depends(get_session),
    camera_service: CameraService = Depends(get_camera_service),
):
    camera_ids = await get_visible_camera_ids(user, session, camera_service)
    if camera_ids is not None and (
        not camera_ids or (camera_id is not None and camera_id not in camera_ids)
    ):
        return []
    try:
        recordings = await service.search(camera_id, day)
        if camera_ids is None:
            return recordings
        return [recording for recording in recordings if recording.camera_id in camera_ids]
    except FtpRecordingUnavailableError as error:
        raise HTTPException(
            status_code=503,
            detail="El catálogo de grabaciones no está disponible temporalmente.",
            headers={"Retry-After": "30"},
        ) from error

@router.get("/recordings/{recording_id}", response_model=RecordingResponse)
async def get_recording(
    recording_id: int,
    service: RecordingService = Depends(get_recording_service),
    user: UserModel = Depends(require_recording_access),
    session: AsyncSession = Depends(get_session),
    camera_service: CameraService = Depends(get_camera_service),
):
    camera_ids = await get_visible_camera_ids(user, session, camera_service)
    if camera_ids is not None and not camera_ids:
        raise HTTPException(status_code=404, detail="Recording not found")
    recording = await service.get(recording_id)
    if recording is None or (camera_ids is not None and recording.camera_id not in camera_ids):
        raise HTTPException(status_code=404, detail="Recording not found")
    return recording

@router.get("/recordings/{recording_id}/stream")
async def stream_recording(
    recording_id: int,
    request: Request,
    service: RecordingService = Depends(get_recording_service),
    user: UserModel = Depends(require_recording_access),
    session: AsyncSession = Depends(get_session),
    camera_service: CameraService = Depends(get_camera_service),
):
    camera_ids = await get_visible_camera_ids(user, session, camera_service)
    if camera_ids is not None and not camera_ids:
        raise HTTPException(status_code=404, detail="Recording not found")
    recording = await service.get(recording_id)
    if recording is None or (camera_ids is not None and recording.camera_id not in camera_ids):
        raise HTTPException(status_code=404, detail="Recording not found")
    header = request.headers.get("range", "bytes=0-")
    try:
        start = int(header.replace("bytes=", "").split("-")[0] or 0)
        file, total = storage.open_range(recording.path, start)
    except (ValueError, OSError, StorageError) as error:
        raise HTTPException(status_code=404, detail=f"Recording file unavailable: {error}")
    end = total - 1
    if "-" in header and header.split("-")[1]: end = min(int(header.split("-")[1]), total - 1)
    length = end - start + 1
    def chunks():
        remaining = length
        try:
            while remaining:
                data = file.read(min(1024 * 1024, remaining))
                if not data: break
                remaining -= len(data)
                yield data
        finally: file.close()
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(length), "Content-Range": f"bytes {start}-{end}/{total}"}
    return StreamingResponse(chunks(), status_code=206 if start or end < total - 1 else 200, media_type="video/mp4", headers=headers)
