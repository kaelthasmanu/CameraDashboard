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
        ftp = FTP(); ftp.connect(settings.ftp_host, settings.ftp_port, timeout=15); ftp.login(settings.ftp_user, settings.ftp_password)
        size = ftp.size(path)
        stream = ftp.transfercmd(f"RETR {path}", rest=start)
        return _FtpStream(stream, ftp), size

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
