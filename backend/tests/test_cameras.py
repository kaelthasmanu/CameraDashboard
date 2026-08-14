import asyncio
from app.application.camera_service import CameraService
from app.infrastructure.camera_repository import InMemoryCameraRepository
from app.application.recording_service import RecordingService
from app.infrastructure.recording_repository import InMemoryRecordingRepository

def test_lists_demo_cameras():
    cameras = asyncio.run(CameraService(InMemoryCameraRepository()).list_cameras())
    assert len(cameras) == 4
    assert cameras[0].name == "Entrada principal"

def test_filters_recordings_by_camera():
    recordings = asyncio.run(RecordingService(InMemoryRecordingRepository()).search(camera_id=1))
    assert recordings
    assert all(recording.camera_id == 1 for recording in recordings)
