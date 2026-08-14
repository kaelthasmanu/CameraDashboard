import asyncio
from app.application.camera_service import CameraService
from app.infrastructure.camera_repository import InMemoryCameraRepository
from app.application.recording_service import RecordingService
from app.infrastructure.recording_repository import InMemoryRecordingRepository

def test_lists_mediamtx_cameras():
    cameras = asyncio.run(CameraService(InMemoryCameraRepository()).list_cameras())
    assert len(cameras) == 2
    assert [camera.stream_url for camera in cameras] == [
        "http://localhost:8888/cam01/index.m3u8",
        "http://localhost:8888/cam02/index.m3u8",
    ]
    assert [camera.name for camera in cameras] == ["Cámara 01", "Cámara 02"]

def test_filters_recordings_by_camera():
    recordings = asyncio.run(RecordingService(InMemoryRecordingRepository()).search(camera_id=1))
    assert recordings
    assert all(recording.camera_id == 1 for recording in recordings)
