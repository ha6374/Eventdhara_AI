import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict


class MetadataBase(BaseModel):
    name: str
    short_description: str
    long_description: str
    inclusion: Optional[List[str]] = []
    faq: Optional[List[dict]] = []
    note: Optional[str] = None
    keywords: Optional[List[str]] = []
    tags: Optional[List[str]] = []
    custom_fields: Optional[Dict[str, Any]] = None


class MetadataCreate(MetadataBase):
    image_id: int


class MetadataUpdate(BaseModel):
    name: Optional[str] = None
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    inclusion: Optional[List[str]] = None
    faq: Optional[List[dict]] = None
    note: Optional[str] = None
    keywords: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None


class MetadataResponse(BaseModel):
    id: int
    image_id: int
    name: str
    short_description: str
    long_description: str
    inclusion: Optional[List[str]] = []
    faq: Optional[List[dict]] = []
    note: Optional[str] = None
    keywords: Optional[List[str]] = []
    tags: Optional[List[str]] = []
    custom_fields: Optional[Dict[str, Any]] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    image_filename: Optional[str] = None
    original_filename: Optional[str] = None
    image_url: Optional[str] = None
    photo: Optional[str] = None
    category_name: Optional[str] = None
    approval_status: Optional[str] = None
    processing_status: Optional[str] = "COMPLETED"
    message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
