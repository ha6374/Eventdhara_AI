from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.category_service import CategoryService
from app.repositories.category_repo import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse, CategoryTreeNode

router = APIRouter()


@router.get("/tree", response_model=List[CategoryTreeNode])
def get_category_tree(active_only: bool = False, db: Session = Depends(get_db)):
    """Fetch complete hierarchical category tree with image counts."""
    service = CategoryService(db)
    return service.get_category_tree(active_only=active_only)


@router.get("/", response_model=List[CategoryResponse])
def get_categories(
    active_only: bool = False,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all categories with optional search."""
    repo = CategoryRepository(db)
    items = repo.get_all(active_only=active_only, search=search)
    counts = repo.get_image_counts()
    results = []
    for cat in items:
        resp = CategoryResponse.model_validate(cat)
        resp.image_count = counts.get(cat.id, 0)
        results.append(resp)
    return results


@router.get("/{category_id}")
def get_category(category_id: int, db: Session = Depends(get_db)):
    """Fetch category details with breadcrumbs and child categories."""
    service = CategoryService(db)
    data = service.get_category_details(category_id)
    if not data:
        raise HTTPException(status_code=404, detail="Category not found")
    return data


@router.post("/", response_model=CategoryResponse)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    """Add a new category or subcategory."""
    repo = CategoryRepository(db)
    if payload.parent_id:
        parent = repo.get_by_id(payload.parent_id)
        if not parent:
            raise HTTPException(status_code=400, detail="Parent category does not exist")

    created = repo.create(payload)
    return created


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db)):
    """Update category details or activation state."""
    repo = CategoryRepository(db)
    cat = repo.get_by_id(category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    if payload.parent_id and payload.parent_id == category_id:
        raise HTTPException(status_code=400, detail="A category cannot be its own parent")

    updated = repo.update(cat, payload)
    return updated


@router.delete("/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    """Delete a category and cascade-manage subcategories."""
    repo = CategoryRepository(db)
    success = repo.delete(category_id)
    if not success:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"success": True, "message": "Category successfully deleted"}


@router.post("/seed")
def seed_categories(db: Session = Depends(get_db)):
    """Seed canonical categories from project specifications."""
    service = CategoryService(db)
    service.seed_initial_categories()
    return {"success": True, "message": "Canonical categories initialized"}
