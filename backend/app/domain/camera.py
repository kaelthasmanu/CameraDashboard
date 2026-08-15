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
    # A lower-bitrate feed intended for multi-camera grids.  ``None`` keeps
    # older MediaMTX configurations compatible: consumers can use stream_url.
    preview_url: str | None = None
