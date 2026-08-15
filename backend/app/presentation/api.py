from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from ..application.camera_service import CameraService
from ..infrastructure.camera_repository import InMemoryCameraRepository
from .schemas import CameraResponse
from ..application.recording_service import RecordingService
from ..infrastructure.recording_repository import FtpRecordingRepository
from .schemas import RecordingResponse
from ..infrastructure.storage import FileStorage, StorageError

router = APIRouter()
repository = InMemoryCameraRepository()
recording_repository = FtpRecordingRepository()
storage = FileStorage()

def get_camera_service() -> CameraService:
    return CameraService(repository)

def get_recording_service() -> RecordingService:
    return RecordingService(recording_repository)

@router.get("/cameras", response_model=list[CameraResponse])
async def list_cameras(service: CameraService = Depends(get_camera_service)):
    return await service.list_cameras()

@router.get("/cameras/{camera_id}", response_model=CameraResponse)
async def get_camera(camera_id: int, service: CameraService = Depends(get_camera_service)):
    camera = await service.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera

@router.get("/recordings", response_model=list[RecordingResponse])
async def list_recordings(camera_id: int | None = None, day: date | None = None, service: RecordingService = Depends(get_recording_service)):
    return await service.search(camera_id, day)

@router.get("/recordings/{recording_id}", response_model=RecordingResponse)
async def get_recording(recording_id: int, service: RecordingService = Depends(get_recording_service)):
    recording = await service.get(recording_id)
    if recording is None:
        raise HTTPException(status_code=404, detail="Recording not found")
    return recording

@router.get("/recordings/{recording_id}/stream")
async def stream_recording(recording_id: int, request: Request, service: RecordingService = Depends(get_recording_service)):
    recording = await service.get(recording_id)
    if recording is None:
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
