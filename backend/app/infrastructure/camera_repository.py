from datetime import datetime, timezone
import hashlib
import logging
from pathlib import Path
from urllib.parse import quote, urlparse
import httpx
import yaml
from ..domain.camera import Camera, CameraStatus
from .settings import settings


PREVIEW_PATH_SUFFIX = "_preview"
DYNAMIC_CAMERA_ID_OFFSET = 1_000_000_000
logger = logging.getLogger(__name__)


class InMemoryCameraRepository:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self._transport = transport
        self._cameras, self._detection_sources = self._load_from_mediamtx()

    def _load_from_mediamtx(self) -> tuple[list[Camera], dict[int, str]]:
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
        detection_sources: dict[int, str] = {}
        now = datetime.now(timezone.utc)
        for path_name, path_config in paths.items():
            # Preview paths are paired with their main path below and must not
            # appear as independent cameras in the dashboard.
            if path_name.endswith(PREVIEW_PATH_SUFFIX):
                continue
            if not isinstance(path_config, dict) or not path_config.get("source"):
                continue
            source = str(path_config["source"])
            if source.strip().lower() == "publisher":
                continue
            parsed_source = urlparse(source)
            model = parsed_source.hostname or parsed_source.scheme.upper() or "MediaMTX"
            preview_path_name = f"{path_name}{PREVIEW_PATH_SUFFIX}"
            preview_path_config = paths.get(preview_path_name)
            preview_url = None
            if isinstance(preview_path_config, dict) and preview_path_config.get("source"):
                preview_url = f"{webrtc_base_url}/{preview_path_name}/whep"
            camera_id = len(cameras) + 1
            cameras.append(Camera(
                id=camera_id,
                name=str(path_name),
                location=f"MediaMTX / {path_name}",
                model=model,
                # MediaMTX exposes WHEP at /<path>/whep; <path> is the YAML key.
                stream_url=f"{webrtc_base_url}/{quote(str(path_name), safe='/')}/whep",
                status=CameraStatus.ONLINE,
                last_seen=now,
                preview_url=preview_url,
            ))
            detection_sources[camera_id] = source
        return cameras, detection_sources

    async def _active_rtmp_paths(self) -> list[dict[str, object]]:
        api_url = f"{settings.mediamtx_api_url.rstrip('/')}/v3/paths/list"
        credentials = None
        if settings.mediamtx_api_username or settings.mediamtx_api_password:
            credentials = (settings.mediamtx_api_username, settings.mediamtx_api_password)

        async with httpx.AsyncClient(
            transport=self._transport,
            timeout=settings.mediamtx_api_timeout_seconds,
            auth=credentials,
        ) as client:
            response = await client.get(api_url, params={"page": 0, "itemsPerPage": 100})
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("items", []), list):
                raise ValueError("Unexpected MediaMTX paths response")

            paths = list(payload.get("items", []))
            page_count = int(payload.get("pageCount", 1))
            for page in range(1, page_count):
                response = await client.get(
                    api_url,
                    params={"page": page, "itemsPerPage": 100},
                )
                response.raise_for_status()
                page_payload = response.json()
                if not isinstance(page_payload, dict) or not isinstance(page_payload.get("items", []), list):
                    raise ValueError("Unexpected MediaMTX paths response")
                paths.extend(page_payload.get("items", []))
            return [path for path in paths if isinstance(path, dict)]

    @staticmethod
    def _dynamic_camera_id(path_name: str) -> int:
        digest = hashlib.sha256(path_name.encode("utf-8")).digest()
        return DYNAMIC_CAMERA_ID_OFFSET + int.from_bytes(digest[:6], "big")

    async def list(self):
        try:
            active_paths = await self._active_rtmp_paths()
        except (httpx.HTTPError, ValueError, TypeError) as error:
            logger.warning("Could not refresh dynamic cameras from MediaMTX: %s", error)
            return self._cameras

        cameras = list(self._cameras)
        configured_names = {camera.name for camera in self._cameras}
        webrtc_base_url = settings.mediamtx_webrtc_public_url.rstrip("/")
        now = datetime.now(timezone.utc)
        for path in active_paths:
            path_name = path.get("name")
            source = path.get("source")
            online = path.get("online", path.get("ready", False))
            if (
                not isinstance(path_name, str)
                or not path_name
                or path_name in configured_names
                or path_name.endswith(PREVIEW_PATH_SUFFIX)
                or online is not True
                or not isinstance(source, dict)
                or source.get("type") not in {"rtmpConn", "rtmpsConn"}
            ):
                continue

            encoded_path = quote(path_name, safe="/")
            cameras.append(Camera(
                id=self._dynamic_camera_id(path_name),
                name=path_name,
                location=f"MediaMTX / {path_name}",
                model="RTMP Publisher",
                stream_url=f"{webrtc_base_url}/{encoded_path}/whep",
                status=CameraStatus.ONLINE,
                last_seen=now,
            ))
        return cameras

    async def get(self, camera_id):
        cameras = await self.list()
        return next((camera for camera in cameras if camera.id == camera_id), None)

    async def list_detection_sources(self) -> dict[int, str]:
        return self._detection_sources.copy()
