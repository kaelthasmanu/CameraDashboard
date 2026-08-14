from datetime import datetime
from pydantic import BaseModel, ConfigDict
from ..domain.camera import CameraStatus

class CameraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    location: str
    model: str
    stream_url: str
    status: CameraStatus
    enabled: bool
    last_seen: datetime | None

class HealthResponse(BaseModel):
    status: str

class RecordingResponse(BaseModel):
    id: int
    camera_id: int
    filename: str
    start_time: datetime
    end_time: datetime
    size_bytes: int
    duration_seconds: int
