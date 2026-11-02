import math
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.image import ImageItem
from app.models.audit import AuditLog
from app.schemas.image import ImageResponse, ImageListResponse, ImageStatusUpdate, ImageBulkAction
from app.repositories.image_repo import ImageRepository
from app.services.duplicate_service import DuplicateService
from app.services.metadata_service import MetadataService
from app.services.drive_service import GoogleDriveService

router = APIRouter()


@router.get("/", response_model=ImageListResponse)
def list_images(
    status: Optional[str] = None,
    category_id: Optional[int] = None,
    quality_status: Optional[str] = None,
    is_duplicate: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db)
):
    """Fetch paginated image collection with multi-factor filtering."""
    repo = ImageRepository(db)
    items, total = repo.list_images(
        status=status,
        category_id=category_id,
        quality_status=quality_status,
        is_duplicate=is_duplicate,
        search=search,
        page=page,
        size=size,
        sort_by=sort_by,
        sort_order=sort_order
    )

    results = []
    for img in items:
        resp = ImageResponse.model_validate(img)
        if img.category:
            resp.category_name = img.category.name
        results.append(resp)

    pages = math.ceil(total / size) if size > 0 else 1
    return ImageListResponse(
        items=results,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/{image_id}", response_model=ImageResponse)
def get_image(image_id: int, db: Session = Depends(get_db)):
    """Fetch detailed image record."""
    repo = ImageRepository(db)
    img = repo.get_by_id(image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    resp = ImageResponse.model_validate(img)
    if img.category:
        resp.category_name = img.category.name
    return resp


@router.patch("/{image_id}/status", response_model=ImageResponse)
def update_image_status(
    image_id: int,
    payload: ImageStatusUpdate,
    db: Session = Depends(get_db)
):
    """
    Manually update image status (e.g., from Review Queue to Approved or Rejected).
    Rule: Manual approval must recheck duplicate status!
    """
    repo = ImageRepository(db)
    img = repo.get_by_id(image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    new_status = payload.status.upper()

    # Rule: Manual approval must recheck duplicate status
    if new_status == "APPROVED":
        dup_service = DuplicateService(db)
        is_dup, orig, sim, dup_type = dup_service.check_global_duplicate(img.sha256, img.phash, exclude_id=img.id)
        if is_dup:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot approve image #{img.id}: It is a duplicate of #{orig.id} ({sim:.1f}% similarity)."
            )

    old_status = img.status
    img.status = new_status
    if payload.category_id:
        img.category_id = payload.category_id
    if payload.reason:
        if new_status == "REJECTED":
            img.rejection_reason = payload.reason
        else:
            img.review_reason = payload.reason

    db.commit()
    db.refresh(img)

    # Audit log
    audit = AuditLog(
        action="UPDATE_STATUS",
        image_id=img.id,
        details=f"Status changed from {old_status} to {new_status}. Reason: {payload.reason or 'Manual review action'}"
    )
    db.add(audit)
    db.commit()

    resp = ImageResponse.model_validate(img)
    if img.category:
        resp.category_name = img.category.name
    return resp


@router.post("/bulk-action")
def bulk_image_action(payload: ImageBulkAction, db: Session = Depends(get_db)):
    """
    Execute bulk batch actions across multiple selected images.
    """
    action = payload.action.upper()
    images = db.query(ImageItem).filter(ImageItem.id.in_(payload.image_ids)).all()
    dup_service = DuplicateService(db)
    meta_service = MetadataService(db)
    drive_service = GoogleDriveService(db)

    success_count = 0
    failed_count = 0
    messages = []

    for img in images:
        try:
            if action == "APPROVE":
                # Recheck duplicate status
                is_dup, orig, sim, _ = dup_service.check_global_duplicate(img.sha256, img.phash, exclude_id=img.id)
                if is_dup:
                    failed_count += 1
                    messages.append(f"Image #{img.id} is duplicate of #{orig.id}")
                    continue
                img.status = "APPROVED"
                success_count += 1
            elif action == "REJECT":
                img.status = "REJECTED"
                img.rejection_reason = payload.reason or "Bulk rejected by operator"
                success_count += 1
            elif action == "MARK_REVIEW":
                img.status = "REVIEW_REQUIRED"
                img.review_reason = payload.reason or "Marked for review in bulk"
                success_count += 1
            elif action == "ASSIGN_CATEGORY":
                if payload.category_id:
                    img.category_id = payload.category_id
                    success_count += 1
            elif action == "GENERATE_METADATA":
                if img.status == "APPROVED":
                    meta_service.generate_for_image(img.id)
                    success_count += 1
                else:
                    failed_count += 1
            elif action == "UPLOAD_DRIVE":
                if img.status == "APPROVED":
                    res = drive_service.upload_approved_image(img.id)
                    if res.get("success"):
                        success_count += 1
                    else:
                        failed_count += 1
                else:
                    failed_count += 1
        except Exception as e:
            failed_count += 1
            messages.append(f"Error on #{img.id}: {str(e)}")

    db.commit()

    return {
        "success": True,
        "action": action,
        "processed_count": len(images),
        "success_count": success_count,
        "failed_count": failed_count,
        "messages": messages
    }
