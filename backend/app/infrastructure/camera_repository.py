from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import yaml
from ..domain.camera import Camera, CameraStatus
from .settings import settings


PREVIEW_PATH_SUFFIX = "_preview"


class InMemoryCameraRepository:
    def __init__(self):
        self._cameras = self._load_from_mediamtx()

    def _load_from_mediamtx(self) -> list[Camera]:
        config_path = Path(settings.mediamtx_config_path)
        if not config_path.exists():
            # Allows pytest/uvicorn to run from a local checkout.
            config_path = Path(__file__).resolve().parents[3] / "mediamtx.yml"
        if not config_path.exists():
            raise FileNotFoundError(f"MediaMTX config not found: {config_path}")

        with config_path.open(encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file) or {}
        paths = config.get("paths") or {}
        if not isinstance(paths, dict):
            raise ValueError("mediamtx.yml: 'paths' must be a mapping")

        webrtc_base_url = settings.mediamtx_webrtc_public_url.rstrip("/")
        cameras: list[Camera] = []
        now = datetime.now(timezone.utc)
        for path_name, path_config in paths.items():
            # Preview paths are paired with their main path below and must not
            # appear as independent cameras in the dashboard.
            if path_name.endswith(PREVIEW_PATH_SUFFIX):
                continue
            if not isinstance(path_config, dict) or not path_config.get("source"):
                continue
            source = str(path_config["source"])
            parsed_source = urlparse(source)
            model = parsed_source.hostname or parsed_source.scheme.upper() or "MediaMTX"
            preview_path_name = f"{path_name}{PREVIEW_PATH_SUFFIX}"
            preview_path_config = paths.get(preview_path_name)
            preview_url = None
            if isinstance(preview_path_config, dict) and preview_path_config.get("source"):
                preview_url = f"{webrtc_base_url}/{preview_path_name}/whep"
            cameras.append(Camera(
                id=len(cameras) + 1,
                name=str(path_name),
                location=f"MediaMTX / {path_name}",
                model=model,
                # MediaMTX exposes WHEP at /<path>/whep; <path> is the YAML key.
                stream_url=f"{webrtc_base_url}/{path_name}/whep",
                status=CameraStatus.ONLINE,
                last_seen=now,
                preview_url=preview_url,
            ))
        return cameras

    async def list(self):
        return self._cameras

    async def get(self, camera_id):
        return next((camera for camera in self._cameras if camera.id == camera_id), None)
