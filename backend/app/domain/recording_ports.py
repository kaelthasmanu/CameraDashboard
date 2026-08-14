from datetime import date
from typing import Protocol
from .recording import Recording

class RecordingRepository(Protocol):
    async def search(self, camera_id: int | None = None, day: date | None = None) -> list[Recording]: ...
    async def get(self, recording_id: int) -> Recording | None: ...
