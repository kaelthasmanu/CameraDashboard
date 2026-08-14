from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

class CameraStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

@dataclass(frozen=True)
class Camera:
    id: int
    name: str
    location: str
    model: str
    stream_url: str
    status: CameraStatus = CameraStatus.UNKNOWN
    enabled: bool = True
    last_seen: datetime | None = None
