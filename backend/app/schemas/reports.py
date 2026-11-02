from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class SystemSettingsSchema(BaseModel):
    min_image_width: int
    min_image_height: int
    min_file_size_kb: int
    blur_threshold: float
    phash_threshold: int
    ai_confidence_threshold: float
    gemini_model: str
    gemini_api_key_configured: bool
    google_drive_configured: bool
    storage_root: str
    environment: str


class SystemSettingsUpdate(BaseModel):
    min_image_width: Optional[int] = None
    min_image_height: Optional[int] = None
    min_file_size_kb: Optional[int] = None
    blur_threshold: Optional[float] = None
    phash_threshold: Optional[int] = None
    ai_confidence_threshold: Optional[float] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None


class ReportSummary(BaseModel):
    period: str
    total_processed: int
    total_approved: int
    total_rejected: int
    total_review: int
    total_duplicates: int
    rejection_breakdown: Dict[str, int]
    category_breakdown: Dict[str, int]
