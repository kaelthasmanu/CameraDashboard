from datetime import date, datetime, timedelta, timezone
from ftplib import FTP, all_errors, error_perm
import re
import unicodedata
import zlib
from ..domain.recording import Recording
from .settings import settings

# Los equipos de grabación suelen usar ``<cámara>_<canal>_<fecha>.mp4``.
# El nombre de cámara puede incluir guiones, espacios y guiones bajos; por eso
# sólo tomamos como separador el último que antecede a la fecha.
# ``14`` es la cantidad de dígitos de ``AAAAMMDDhhmmss``; no significa que
# sólo se acepten vídeos del día 14. El día se elige con la carpeta YYYY/MM/DD.
TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"
TIMESTAMP_DIGITS = 14
FILENAME_PATTERN = re.compile(
    rf"^(?P<prefix>.+?)[_\-\s]+(?P<timestamp>\d{{{TIMESTAMP_DIGITS}}})\.mp4$",
    re.IGNORECASE,
)
CHANNEL_SUFFIX_PATTERN = re.compile(r"^(?P<camera>.+?)[_\-\s]+\d{1,3}$")


class FtpRecordingUnavailableError(RuntimeError):
    """The FTP catalog cannot be reached or listed at the moment.

    This deliberately keeps the original network error out of the public API
    response.  The caller can use the exception type to return a retryable
    service-unavailable response instead of an unrelated 500.
    """

    def __init__(self, operation: str):
        self.operation = operation
        super().__init__(f"FTP recording catalog unavailable during {operation}")


def parse_recording_filename(filename: str) -> tuple[str, datetime] | None:
    """Return the source camera prefix and UTC start time for an MP4 filename.

    Accepted examples include ``NodoRedes_00_20260815100739.mp4`` and
    ``RLC-810A_00_20260815060334.MP4``.  A malformed date or a non-MP4 file
    is deliberately ignored instead of aborting the complete FTP index.
    """
    match = FILENAME_PATTERN.match(filename)
    if not match:
        return None

    prefix = match.group("prefix").strip()
    if not prefix:
        return None
    try:
        start = datetime.strptime(match.group("timestamp"), TIMESTAMP_FORMAT)
    except ValueError:
        return None
    return prefix, start.replace(tzinfo=timezone.utc)


def _normalise_camera_prefix(prefix: str) -> str:
    """Match camera labels independently of case, accents and separators."""
    decomposed = unicodedata.normalize("NFKD", prefix).casefold()
    return "".join(character for character in decomposed if character.isalnum())


def _camera_prefix_candidates(prefix: str) -> tuple[str, ...]:
    """Return the full recorder label and, when present, the label without channel.

    Keeping the full label first preserves existing mappings such as
    ``RLC-810A_00:1`` while also allowing ``NodoRedes:1`` to match
    ``NodoRedes_00_...mp4``.
    """
    candidates = [prefix]
    channel_match = CHANNEL_SUFFIX_PATTERN.match(prefix)
    if channel_match:
        camera_name = channel_match.group("camera").strip()
        if camera_name:
            candidates.append(camera_name)
    return tuple(candidates)


def _recording_directory(target: date) -> str:
    """Return the day folder, for example ``/2026/08/15``.

    The selected calendar day controls this path. It is independent of the
    timestamp digit count in the filename, so the same code works for the
    14th, 15th, 16th and every other valid date.
    """
    return f"/{target:%Y/%m/%d}"

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
            normalised_prefix = _normalise_camera_prefix(prefix)
            if not normalised_prefix:
                continue
            try:
                parsed_camera_id = int(camera_id.strip())
            except ValueError:
                continue
            if parsed_camera_id > 0:
                result[normalised_prefix] = parsed_camera_id
        return result

    def _camera_id_for_prefix(self, prefix: str) -> int | None:
        for candidate in _camera_prefix_candidates(prefix):
            mapped_camera_id = self._prefixes.get(_normalise_camera_prefix(candidate))
            if mapped_camera_id is not None:
                return mapped_camera_id
        # Mantiene el comportamiento demo cuando no se configuró ningún alias.
        return 1 if not self._prefixes else None

    def _connect(self) -> FTP:
        ftp = FTP()
        try:
            ftp.connect(settings.ftp_host, settings.ftp_port, timeout=15)
            if settings.ftp_anonymous:
                ftp.login("anonymous", settings.ftp_password or "anonymous@localhost")
            else:
                ftp.login(settings.ftp_user, settings.ftp_password)
        except all_errors as error:
            try:
                ftp.close()
            except OSError:
                pass
            raise FtpRecordingUnavailableError("connection") from error
        return ftp

    def _list_entries(self, ftp: FTP, remote_directory: str):
        try:
            return list(ftp.mlsd(remote_directory, facts=["type", "size"]))
        except error_perm:
            # Algunos servidores FTP no implementan MLSD; NLST conserva
            # compatibilidad con ellos sin tratarlo como una indisponibilidad.
            return self._list_entries_with_nlst(ftp, remote_directory)
        except all_errors as error:
            raise FtpRecordingUnavailableError("directory listing") from error

    def _list_entries_with_nlst(self, ftp: FTP, remote_directory: str):
        try:
            entries = []
            for name in ftp.nlst(remote_directory):
                try:
                    size = ftp.size(name)
                except error_perm:
                    # SIZE puede no estar disponible para directorios o en
                    # servidores mínimos. El vídeo sigue siendo indexable.
                    size = 0
                entries.append((name.rsplit("/", 1)[-1], {"type": "file", "size": str(size or 0)}))
            return entries
        except all_errors as error:
            raise FtpRecordingUnavailableError("directory listing") from error

    def _remote_directory(self, directory: str) -> str:
        root = settings.ftp_root.strip().rstrip("/")
        return f"{root}{directory}" if root else directory

    async def search(self, camera_id: int | None = None, day: date | None = None) -> list[Recording]:
        target = day or datetime.now(timezone.utc).date()
        # Las grabaciones están bajo FTP_ROOT/YYYY/MM/DD. La ruta guardada en
        # Recording queda relativa a FTP_ROOT para que FileStorage no duplique
        # el prefijo al servir el archivo.
        directory = _recording_directory(target)
        remote_directory = self._remote_directory(directory)
        try:
            ftp = self._connect()
        except FtpRecordingUnavailableError:
            raise
        except all_errors as error:
            # También protege implementaciones sustituidas en pruebas o
            # adaptadores que aún arrojen errores nativos de socket/FTP.
            raise FtpRecordingUnavailableError("connection") from error
        try:
            entries = self._list_entries(ftp, remote_directory)
        finally:
            try:
                ftp.quit()
            except all_errors:
                # La lista ya se obtuvo; no convertir un cierre fallido en un
                # error visible para el usuario.
                pass
        items: list[Recording] = []
        for filename, facts in entries:
            if facts.get("type") != "file":
                continue
            parsed_filename = parse_recording_filename(filename)
            if parsed_filename is None:
                continue
            prefix, start = parsed_filename
            mapped_camera_id = self._camera_id_for_prefix(prefix)
            if mapped_camera_id is None or (camera_id is not None and mapped_camera_id != camera_id):
                continue
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
