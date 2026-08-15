from datetime import date, datetime, timedelta, timezone
from ftplib import FTP
import re
import zlib
from ..domain.recording import Recording
from .settings import settings

FILENAME_PATTERN = re.compile(r"^(?P<prefix>.+)_(?P<timestamp>\d{14})\.mp4$", re.IGNORECASE)

class FtpRecordingRepository:
    """Indexes /<year>/<month>/<day>/*.mp4 from the configured FTP root."""
    def __init__(self):
        self._cache: dict[int, Recording] = {}
        self._prefixes = self._parse_prefixes()

    def _parse_prefixes(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for item in settings.ftp_camera_prefixes.split(","):
            if not item.strip() or ":" not in item:
                continue
            prefix, camera_id = item.split(":", 1)
            result[prefix.strip()] = int(camera_id.strip())
        return result

    def _connect(self) -> FTP:
        ftp = FTP(); ftp.connect(settings.ftp_host, settings.ftp_port, timeout=15)
        if settings.ftp_anonymous:
            ftp.login("anonymous", settings.ftp_password or "anonymous@localhost")
        else:
            ftp.login(settings.ftp_user, settings.ftp_password)
        return ftp

    def _remote_directory(self, directory: str) -> str:
        root = settings.ftp_root.strip().rstrip("/")
        return f"{root}{directory}" if root else directory

    async def search(self, camera_id: int | None = None, day: date | None = None) -> list[Recording]:
        target = day or datetime.now(timezone.utc).date()
        # Las grabaciones están bajo FTP_ROOT/YYYY/MM/DD. La ruta guardada en
        # Recording queda relativa a FTP_ROOT para que FileStorage no duplique
        # el prefijo al servir el archivo.
        directory = f"/{target:%Y/%m/%d}"
        remote_directory = self._remote_directory(directory)
        ftp = self._connect()
        try:
            entries = list(ftp.mlsd(remote_directory, facts=["type", "size"]))
        except Exception:
            entries = [(name.rsplit("/", 1)[-1], {"type": "file", "size": str(ftp.size(name))}) for name in ftp.nlst(remote_directory)]
        finally:
            ftp.quit()
        items: list[Recording] = []
        for filename, facts in entries:
            if facts.get("type") != "file" or not filename.lower().endswith(".mp4"):
                continue
            match = FILENAME_PATTERN.match(filename)
            if not match:
                continue
            prefix, timestamp = match.group("prefix"), match.group("timestamp")
            mapped_camera_id = self._prefixes.get(prefix, 1 if len(self._prefixes) == 0 else None)
            if mapped_camera_id is None or (camera_id is not None and mapped_camera_id != camera_id):
                continue
            start = datetime.strptime(timestamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            duration = settings.ftp_recording_duration_seconds
            # Debe ser estable entre peticiones y menor que Number.MAX_SAFE_INTEGER;
            # un hash de Python puede superar el límite seguro de JavaScript.
            recording_id = zlib.crc32(f"{directory}/{filename}".encode("utf-8"))
            item = Recording(recording_id, mapped_camera_id, filename, f"{directory}/{filename}", start, start + timedelta(seconds=duration), int(facts.get("size") or 0), duration)
            self._cache[recording_id] = item; items.append(item)
        return sorted(items, key=lambda item: item.start_time, reverse=True)

    async def get(self, recording_id: int) -> Recording | None:
        return self._cache.get(recording_id)

class InMemoryRecordingRepository:
    def __init__(self):
        day = datetime.now(timezone.utc).date()
        self._items = [Recording(i, (i % 4) + 1, f"cam{(i % 4) + 1:02d}_{10+i:02d}00.mp4", f"/recordings/cam{(i % 4) + 1:02d}/{day}/{i:02d}.mp4", datetime(day.year, day.month, day.day, 10+i, 0, tzinfo=timezone.utc), datetime(day.year, day.month, day.day, 10+i, 30, tzinfo=timezone.utc), 482_193_812, 1800) for i in range(1, 7)]

    async def search(self, camera_id=None, day=None):
        return [item for item in self._items if (camera_id is None or item.camera_id == camera_id) and (day is None or item.start_time.date() == day)]

    async def get(self, recording_id):
        return next((item for item in self._items if item.id == recording_id), None)
