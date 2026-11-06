import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict


class AIClassificationResult(BaseModel):
    predicted_category: str = ""
    matched_subcategory: str = ""
    uploaded_category: str = ""
    category_match: bool = True
    image_quality: str = "HIGH"
    confidence_score: float = 0.0
    approval_status: str = "REVIEW_REQUIRED"
    rejection_reason: str = ""
    review_required: bool = False


class ImageResponse(BaseModel):
    id: int
    uuid: str
    filename: str
    original_filename: str
    file_path: str
    storage_path: str
    file_url: Optional[str] = None
    file_size: int
    width: int
    height: int
    format: str
    sha256: str
    phash: str
    blur_score: Optional[float] = None
    quality_status: str
    status: str
    rejection_reason: Optional[str] = None
    review_reason: Optional[str] = None
    is_duplicate: bool
    duplicate_of_id: Optional[int] = None
    duplicate_similarity: Optional[float] = None
    duplicate_type: Optional[str] = None
    ai_classification: Optional[str] = None
    ai_confidence: Optional[float] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    metadata_status: str
    drive_status: str
    drive_file_id: Optional[str] = None
    drive_url: Optional[str] = None
    drive_uploaded_at: Optional[datetime.datetime] = None
    batch_id: Optional[str] = None
    processing_duration_ms: Optional[float] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ImageListResponse(BaseModel):
    items: List[ImageResponse]
    total: int
    page: int
    size: int
    pages: int


class ImageStatusUpdate(BaseModel):
    status: str  # APPROVED, REJECTED, REVIEW_REQUIRED
    category_id: Optional[int] = None
    reason: Optional[str] = None
    custom_feedback: Optional[str] = None


class ImageRejectRequest(BaseModel):
    rejection_reason: str
    custom_feedback: Optional[str] = None
    user_id: Optional[str] = "operator"


class ImageBulkAction(BaseModel):
    image_ids: List[int]
    action: str  # APPROVE, REJECT, MARK_REVIEW, ASSIGN_CATEGORY, RETRY_AI, RETRY_METADATA, UPLOAD_DRIVE, DELETE
    category_id: Optional[int] = None
    reason: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: int
    image_id: int
    original_filename: str
    original_category: Optional[str] = None
    predicted_category: Optional[str] = None
    rejection_reason: str
    custom_feedback: Optional[str] = None
    ai_confidence_score: Optional[float] = None
    insights: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
