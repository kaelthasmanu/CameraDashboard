from datetime import datetime, timezone
from ..domain.camera import Camera, CameraStatus

class InMemoryCameraRepository:
    def __init__(self):
        self._cameras = [
            Camera(1, "Entrada principal", "Acceso norte", "Hikvision DS-2CD", "https://demo.invalid/cam-1", CameraStatus.ONLINE, last_seen=datetime.now(timezone.utc)),
            Camera(2, "Almacén", "Nave logística", "Hikvision DS-2CD", "https://demo.invalid/cam-2", CameraStatus.ONLINE, last_seen=datetime.now(timezone.utc)),
            Camera(3, "Parking", "Exterior", "Hikvision DS-2CD", "https://demo.invalid/cam-3", CameraStatus.OFFLINE),
            Camera(4, "Recepción", "Edificio central", "Hikvision DS-2CD", "https://demo.invalid/cam-4", CameraStatus.ONLINE, last_seen=datetime.now(timezone.utc)),
        ]

    async def list(self):
        return self._cameras

    async def get(self, camera_id):
        return next((camera for camera in self._cameras if camera.id == camera_id), None)
