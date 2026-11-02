import os
from fastapi import APIRouter
from app.core.config import settings
from app.schemas.reports import SystemSettingsSchema, SystemSettingsUpdate

router = APIRouter()


@router.get("/", response_model=SystemSettingsSchema)
def get_system_settings():
    """Retrieve operational system settings and integration status."""
    has_gemini = bool(os.getenv("GEMINI_API_KEY", settings.GEMINI_API_KEY).strip())
    has_drive = bool(settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip() or True)

    return SystemSettingsSchema(
        min_image_width=settings.MIN_IMAGE_WIDTH,
        min_image_height=settings.MIN_IMAGE_HEIGHT,
        min_file_size_kb=settings.MIN_FILE_SIZE_KB,
        blur_threshold=settings.BLUR_THRESHOLD,
        phash_threshold=settings.PHASH_THRESHOLD,
        ai_confidence_threshold=settings.AI_CONFIDENCE_THRESHOLD,
        gemini_model=settings.GEMINI_MODEL,
        gemini_api_key_configured=has_gemini,
        google_drive_configured=has_drive,
        storage_root=settings.STORAGE_ROOT,
        environment=settings.ENVIRONMENT
    )


@router.put("/", response_model=SystemSettingsSchema)
def update_system_settings(payload: SystemSettingsUpdate):
    """Update runtime configurable thresholds."""
    if payload.min_image_width is not None:
        settings.MIN_IMAGE_WIDTH = payload.min_image_width
    if payload.min_image_height is not None:
        settings.MIN_IMAGE_HEIGHT = payload.min_image_height
    if payload.min_file_size_kb is not None:
        settings.MIN_FILE_SIZE_KB = payload.min_file_size_kb
    if payload.blur_threshold is not None:
        settings.BLUR_THRESHOLD = payload.blur_threshold
    if payload.phash_threshold is not None:
        settings.PHASH_THRESHOLD = payload.phash_threshold
    if payload.ai_confidence_threshold is not None:
        settings.AI_CONFIDENCE_THRESHOLD = payload.ai_confidence_threshold
    if payload.gemini_model is not None:
        settings.GEMINI_MODEL = payload.gemini_model
    if payload.gemini_api_key is not None:
        os.environ["GEMINI_API_KEY"] = payload.gemini_api_key
        settings.GEMINI_API_KEY = payload.gemini_api_key
        # Refresh Gemini service
        from app.services.gemini_service import gemini_service
        gemini_service.__init__()

    return get_system_settings()
