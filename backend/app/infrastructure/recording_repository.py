from datetime import date, datetime, timezone
from ..domain.recording import Recording

class InMemoryRecordingRepository:
    def __init__(self):
        day = datetime.now(timezone.utc).date()
        self._items = [Recording(i, (i % 4) + 1, f"cam{(i % 4) + 1:02d}_{10+i:02d}00.mp4", f"/recordings/cam{(i % 4) + 1:02d}/{day}/{i:02d}.mp4", datetime(day.year, day.month, day.day, 10+i, 0, tzinfo=timezone.utc), datetime(day.year, day.month, day.day, 10+i, 30, tzinfo=timezone.utc), 482_193_812, 1800) for i in range(1, 7)]

    async def search(self, camera_id=None, day=None):
        return [item for item in self._items if (camera_id is None or item.camera_id == camera_id) and (day is None or item.start_time.date() == day)]

    async def get(self, recording_id):
        return next((item for item in self._items if item.id == recording_id), None)
