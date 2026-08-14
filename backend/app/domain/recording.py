from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class Recording:
    id: int
    camera_id: int
    filename: str
    path: str
    start_time: datetime
    end_time: datetime
    size_bytes: int
    duration_seconds: int
