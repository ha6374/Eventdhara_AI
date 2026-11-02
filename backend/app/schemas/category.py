import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    is_active: bool = True


class CategoryCreate(CategoryBase):
    slug: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    is_active: Optional[bool] = None


class CategoryResponse(CategoryBase):
    id: int
    slug: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    image_count: int = 0
    children: List["CategoryResponse"] = []

    model_config = ConfigDict(from_attributes=True)


class CategoryTreeNode(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    is_active: bool
    image_count: int = 0
    depth: int = 0
    children: List["CategoryTreeNode"] = []

    model_config = ConfigDict(from_attributes=True)
