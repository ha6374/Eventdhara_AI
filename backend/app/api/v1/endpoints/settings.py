import os
import re
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.core.config import settings
from app.schemas.reports import SystemSettingsSchema, SystemSettingsUpdate
from app.services.gemini_service import gemini_service

router = APIRouter()


class GeminiKeyUpdate(BaseModel):
    api_key: str


def mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return "Not Configured"
    return f"{key[:6]}...{key[-4:]}"


@router.get("/", response_model=SystemSettingsSchema)
def get_system_settings():
    """Retrieve operational system settings and integration status."""
    current_key = os.getenv("GEMINI_API_KEY", settings.GEMINI_API_KEY).strip()
    has_gemini = bool(current_key)
    has_drive = bool(
        (getattr(settings, "GOOGLE_OAUTH_CLIENT_JSON", None) and os.path.exists(settings.GOOGLE_OAUTH_CLIENT_JSON))
        or (getattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", None) and os.path.exists(settings.GOOGLE_SERVICE_ACCOUNT_JSON))
    )

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


@router.post("/test-gemini")
def test_gemini_api_connection():
    """
    Tests the active Gemini API key against Google GenAI with a live ping.
    Returns status: CONNECTED, QUOTA_OR_BILLING_REQUIRED, INVALID_KEY, or NOT_CONFIGURED.
    """
    return gemini_service.test_connection()


@router.post("/gemini-key")
def update_gemini_api_key(payload: GeminiKeyUpdate):
    """
    Safely updates and persists the Gemini API key, masking it in responses.
    """
    new_key = payload.api_key.strip()
    if not new_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    os.environ["GEMINI_API_KEY"] = new_key
    settings.GEMINI_API_KEY = new_key
    gemini_service.__init__()

    # Update .env file persistently
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()
            if "GEMINI_API_KEY=" in content:
                content = re.sub(r"GEMINI_API_KEY=.*", f"GEMINI_API_KEY={new_key}", content)
            else:
                content += f"\nGEMINI_API_KEY={new_key}\n"
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            pass

    test_res = gemini_service.test_connection()

    return {
        "success": True,
        "masked_key": mask_key(new_key),
        "test_result": test_res,
        "message": "Gemini API key updated successfully."
    }


@router.delete("/gemini-key")
def remove_gemini_api_key():
    """Removes the stored Gemini API key and reverts to heuristic mode."""
    os.environ["GEMINI_API_KEY"] = ""
    settings.GEMINI_API_KEY = ""
    gemini_service.__init__()

    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()
            content = re.sub(r"GEMINI_API_KEY=.*", "GEMINI_API_KEY=", content)
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass

    return {
        "success": True,
        "message": "Gemini API key removed. System reverted to heuristic classification mode."
    }


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
    if payload.gemini_api_key is not None and payload.gemini_api_key.strip():
        os.environ["GEMINI_API_KEY"] = payload.gemini_api_key.strip()
        settings.GEMINI_API_KEY = payload.gemini_api_key.strip()
        gemini_service.__init__()

    return get_system_settings()
