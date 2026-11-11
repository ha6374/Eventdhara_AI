import os
from typing import List, Union, Optional
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "EventDhara AI Data Operations Platform"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "eventdhara-enterprise-secret-key-2026"

    # PostgreSQL Database URL
    DATABASE_URL: str = "postgresql+psycopg2://postgres:123456@localhost:5432/eventdhara_db"
    SQL_ECHO: bool = False

    # Storage Paths
    STORAGE_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "storage"))
    MAX_UPLOAD_SIZE_MB: int = 500

    # ZIP Archive Safety Limits (Anti-ZipBomb & Memory Protection)
    ZIP_MAX_FILES: int = 1000
    ZIP_MAX_TOTAL_UNCOMPRESSED_MB: int = 2048
    ZIP_MAX_FILE_SIZE_MB: int = 50
    ZIP_MAX_COMPRESSION_RATIO: float = 100.0

    # Image Quality & Safety Thresholds
    MIN_IMAGE_WIDTH: int = 800
    MIN_IMAGE_HEIGHT: int = 600
    MAX_IMAGE_WIDTH: int = 12000
    MAX_IMAGE_HEIGHT: int = 12000
    MAX_IMAGE_PIXELS: int = 60_000_000  # 60 Megapixels max
    OPENCV_MAX_PROCESSING_DIMENSION: int = 1920  # Max dimension for cv2 blur/lighting
    BATCH_GC_INTERVAL: int = 10  # Frequency of garbage collection & session expiration
    MIN_FILE_SIZE_KB: int = 50
    BLUR_THRESHOLD: float = 100.0  # Variance of the Laplacian
    PHASH_THRESHOLD: int = 5       # Max Hamming distance for pHash duplicate match
    WATERMARK_DETECTION: bool = False

    # AI (Gemini) Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-3.8-flash"
    AI_CONFIDENCE_THRESHOLD: float = 0.75

    # Google Drive Integration
    GOOGLE_DRIVE_ROOT_FOLDER_NAME: str = "EventDhara_decorations"
    GOOGLE_DRIVE_ROOT_FOLDER_ID: str = "19BGF1jSqlilxTnEDuaZldYb2yp25yedJ"

    GOOGLE_OAUTH_CLIENT_JSON: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "credentials.json")
    )

    GOOGLE_DRIVE_TOKEN_JSON: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "token.json")
    )

    # Dynamic Google Sheets OAuth 2.0 Integration
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "https://eventdhara-ai.onrender.com/api/v1/sheets/oauth/callback"
    GOOGLE_TOKEN_ENCRYPTION_KEY: str = ""
    BACKEND_PUBLIC_URL: str = "https://eventdhara-ai.onrender.com"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://eventdhara-ai-1.onrender.com",
    ]

    @field_validator("STORAGE_ROOT", mode="before")
    def resolve_storage_root(cls, v: Optional[str] = None) -> str:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        if v and isinstance(v, str) and v.strip():
            cleaned = v.strip()
            if os.path.isabs(cleaned):
                return cleaned
            # Strip relative parent traversal so relative paths stay anchored to project root
            clean_sub = cleaned.replace("../", "").replace("..\\", "").lstrip("/\\")
            return os.path.abspath(os.path.join(project_root, clean_sub or "storage"))
        return os.path.abspath(os.path.join(project_root, "storage"))

    @field_validator("CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

    model_config = SettingsConfigDict(
        env_file=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# Ensure storage directories exist
os.makedirs(settings.STORAGE_ROOT, exist_ok=True)
for sub in ["uploads", "extracted", "processed", "approved", "rejected", "duplicates", "exports", "EventDhara"]:
    os.makedirs(os.path.join(settings.STORAGE_ROOT, sub), exist_ok=True)
