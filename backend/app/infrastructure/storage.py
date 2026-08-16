from pathlib import Path
from ftplib import FTP
from typing import BinaryIO
from .settings import settings
import paramiko

class StorageError(Exception): pass

class FileStorage:
    def open_range(self, path: str, start: int = 0) -> tuple[BinaryIO, int]:
        if settings.storage_backend == "local":
            file = Path(path).open("rb"); file.seek(start)
            return file, Path(path).stat().st_size
        if settings.storage_backend == "ftp": return FtpStorage().open_range(path, start)
        if settings.storage_backend == "sftp": return SftpStorage().open_range(path, start)
        raise StorageError("Demo recordings have no backing file")

class FtpStorage:
    def open_range(self, path: str, start: int = 0):
        ftp = FTP()
        try:
            ftp.connect(settings.ftp_host, settings.ftp_port, timeout=15)
            if settings.ftp_anonymous:
                ftp.login(user="anonymous", passwd=settings.ftp_password or "anonymous@localhost")
            else:
                ftp.login(settings.ftp_user, settings.ftp_password)
            # MP4 files are binary, and REST works correctly only in TYPE I.
            ftp.voidcmd("TYPE I")
            remote_path = _ftp_path(path)
            size = ftp.size(remote_path)
            stream = ftp.transfercmd(f"RETR {remote_path}", rest=start)
            return _FtpStream(stream, ftp), size
        except Exception as error:
            try:
                ftp.close()
            except Exception:
                pass
            raise StorageError(f"FTP cannot stream '{path}': {error}") from error

def _ftp_path(path: str) -> str:
    root = settings.ftp_root.strip().rstrip("/")
    clean_path = "/" + path.lstrip("/")
    return clean_path if not root else f"{root}{clean_path}"

class SftpStorage:
    def open_range(self, path: str, start: int = 0):
        transport = paramiko.Transport((settings.ftp_host, settings.ftp_port or 22))
        transport.connect(username=settings.ftp_user, password=settings.ftp_password)
        client = paramiko.SFTPClient.from_transport(transport)
        handle = client.open(path, "rb"); size = client.stat(path).st_size; handle.seek(start)
        return _SftpStream(handle, client, transport), size

class _FtpStream:
    def __init__(self, stream, ftp): self.stream, self.ftp = stream, ftp
    def read(self, size=-1): return self.stream.recv(size if size > 0 else 64 * 1024)
    def close(self):
        self.stream.close(); self.ftp.quit()

class _SftpStream:
    def __init__(self, handle, client, transport): self.handle, self.client, self.transport = handle, client, transport
    def read(self, size=-1): return self.handle.read(size if size > 0 else 64 * 1024)
    def close(self): self.handle.close(); self.client.close(); self.transport.close()
