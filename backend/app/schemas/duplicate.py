from typing import List, Optional
from pydantic import BaseModel
from app.schemas.image import ImageResponse


class DuplicateComparisonItem(BaseModel):
    duplicate_image: ImageResponse
    original_image: Optional[ImageResponse] = None
    similarity_percentage: float
    duplicate_type: str  # EXACT_SHA256 or VISUAL_PHASH
