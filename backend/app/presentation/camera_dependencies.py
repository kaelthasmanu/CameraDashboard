from ..application.camera_service import CameraService
from ..infrastructure.camera_repository import InMemoryCameraRepository
from ..infrastructure.person_detection import PersonRecognitionService


repository = InMemoryCameraRepository()
person_recognition_service = PersonRecognitionService(CameraService(repository))


def get_camera_service() -> CameraService:
    return CameraService(repository)


def get_person_recognition_service() -> PersonRecognitionService:
    return person_recognition_service
