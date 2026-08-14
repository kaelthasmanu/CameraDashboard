from datetime import date
from ..domain.recording import Recording
from ..domain.recording_ports import RecordingRepository

class RecordingService:
    def __init__(self, repository: RecordingRepository):
        self._repository = repository

    async def search(self, camera_id: int | None = None, day: date | None = None) -> list[Recording]:
        return await self._repository.search(camera_id, day)

    async def get(self, recording_id: int) -> Recording | None:
        return await self._repository.get(recording_id)
