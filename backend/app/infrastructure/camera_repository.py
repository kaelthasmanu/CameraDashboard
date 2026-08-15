from datetime import datetime, timezone
import os
from pathlib import Path
from urllib.parse import urlparse
import yaml
from ..domain.camera import Camera, CameraStatus

class InMemoryCameraRepository:
    def __init__(self):
        self._cameras = self._load_from_mediamtx()

    def _load_from_mediamtx(self) -> list[Camera]:
        config_path = Path(os.getenv("MEDIAMTX_CONFIG_PATH", "/app/mediamtx.yml"))
        if not config_path.exists():
            # Permite ejecutar pytest/uvicorn desde el checkout local.
            config_path = Path(__file__).resolve().parents[3] / "mediamtx.yml"
        if not config_path.exists():
            raise FileNotFoundError(f"MediaMTX config not found: {config_path}")

        with config_path.open(encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file) or {}
        paths = config.get("paths") or {}
        if not isinstance(paths, dict):
            raise ValueError("mediamtx.yml: 'paths' must be a mapping")

        webrtc_base_url = os.getenv("MEDIAMTX_WEBRTC_PUBLIC_URL", "http://localhost:8889").rstrip("/")
        cameras: list[Camera] = []
        now = datetime.now(timezone.utc)
        for camera_id, (path_name, path_config) in enumerate(paths.items(), start=1):
            if not isinstance(path_config, dict) or not path_config.get("source"):
                continue
            source = str(path_config["source"])
            parsed_source = urlparse(source)
            model = parsed_source.hostname or parsed_source.scheme.upper() or "MediaMTX"
            cameras.append(Camera(
                id=camera_id,
                name=str(path_name),
                location=f"MediaMTX / {path_name}",
                model=model,
                stream_url=f"{webrtc_base_url}/{path_name}/whep",
                status=CameraStatus.ONLINE,
                last_seen=now,
            ))
        return cameras

    async def list(self):
        return self._cameras

    async def get(self, camera_id):
        return next((camera for camera in self._cameras if camera.id == camera_id), None)
