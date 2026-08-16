from ..application.camera_service import CameraService
from ..infrastructure.camera_repository import InMemoryCameraRepository


repository = InMemoryCameraRepository()


def get_camera_service() -> CameraService:
    return CameraService(repository)
