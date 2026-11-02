import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.image import ImageResponse


class BatchResponse(BaseModel):
    id: str
    original_name: str
    total_files: int
    valid_files: int
    invalid_files: int
    status: str
    error_message: Optional[str] = None
    target_category_id: Optional[int] = None
    created_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UploadResultResponse(BaseModel):
    batch_id: str
    total_received: int
    valid_images: int
    invalid_files: int
    processed_items: List[ImageResponse]
    message: str
