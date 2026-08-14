from datetime import datetime, timezone
import os
from ..domain.camera import Camera, CameraStatus

class InMemoryCameraRepository:
    def __init__(self):
        media_base_url = os.getenv("MEDIAMTX_PUBLIC_URL", "http://localhost:8888").rstrip("/")
        self._cameras = [
            Camera(1, "Cámara 01", "RTSP / cam01", "Hikvision", f"{media_base_url}/cam01/index.m3u8", CameraStatus.ONLINE, last_seen=datetime.now(timezone.utc)),
            Camera(2, "Cámara 02", "RTSP / cam02", "Hikvision", f"{media_base_url}/cam02/index.m3u8", CameraStatus.ONLINE, last_seen=datetime.now(timezone.utc)),
        ]

    async def list(self):
        return self._cameras

    async def get(self, camera_id):
        return next((camera for camera in self._cameras if camera.id == camera_id), None)
