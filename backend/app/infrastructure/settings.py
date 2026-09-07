from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./camera_dashboard.db"
    cors_origins: str = "http://localhost:5173"
    # Exact origins and optional trusted IP networks for browser CORS.
    cors_origin_cidrs: str = ""
    cors_origin_cidr_ports: str = ""
    storage_backend: str = "local"
    ftp_host: str = ""
    ftp_port: int = 21
    ftp_user: str = ""
    ftp_password: str = ""
    ftp_anonymous: bool = False
    ftp_root: str = "/"
    ftp_recording_duration_seconds: int = 1800
    ftp_camera_prefixes: str = ""
    mediamtx_config_path: str = "/app/mediamtx.yml"
    mediamtx_webrtc_public_url: str = "http://localhost:8889"
    frontend_api_url: str = "http://localhost:8000/api/v1"
    jwt_secret_key: str = "change-this-secret-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 60
    auth_cookie_secure: bool = False
    admin_username: str = "admin"
    admin_password: str = "change-me-now"
    person_detection_enabled: bool = True
    person_detection_model: str = "yolo11m.pt"
    person_detection_confidence: float = 0.2
    person_detection_image_size: int = 1280
    person_detection_augment: bool = True
    person_detection_max_detections: int = 100
    person_detection_frame_interval_seconds: float = 0.25
    person_detection_alert_seconds: int = 2
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[3] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

settings = Settings()
