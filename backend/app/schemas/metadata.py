import datetime
from typing import List, Optional, Any
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
    created_at: datetime.datetime
    updated_at: datetime.datetime
    image_filename: Optional[str] = None
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
