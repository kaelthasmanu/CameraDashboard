from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./camera_dashboard.db"
    storage_backend: str = "demo"
    ftp_host: str = ""
    ftp_port: int = 21
    ftp_user: str = ""
    ftp_password: str = ""
    ftp_root: str = "/"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
