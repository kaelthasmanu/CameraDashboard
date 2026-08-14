from ..domain.camera import Camera
from ..domain.ports import CameraRepository

class CameraService:
    def __init__(self, repository: CameraRepository):
        self._repository = repository

    async def list_cameras(self) -> list[Camera]:
        return await self._repository.list()

    async def get_camera(self, camera_id: int) -> Camera | None:
        return await self._repository.get(camera_id)
