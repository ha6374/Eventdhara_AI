from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.image import ImageItem
from app.models.audit import AuditLog
from app.schemas.duplicate import DuplicateComparisonItem
from app.schemas.image import ImageResponse
from app.services.duplicate_service import DuplicateService

router = APIRouter()


@router.get("/", response_model=List[DuplicateComparisonItem])
def list_duplicates(db: Session = Depends(get_db)):
    """
    Fetch all detected duplicate images paired side-by-side with their original reference images.
    """
    dup_images = (
        db.query(ImageItem)
        .filter(ImageItem.is_duplicate == True)
        .order_by(ImageItem.created_at.desc())
        .all()
    )

    results = []
    for dup in dup_images:
        orig = None
        if dup.duplicate_of_id:
            orig = db.query(ImageItem).filter(ImageItem.id == dup.duplicate_of_id).first()

        dup_resp = ImageResponse.model_validate(dup)
        if dup.category:
            dup_resp.category_name = dup.category.name

        orig_resp = None
        if orig:
            orig_resp = ImageResponse.model_validate(orig)
            if orig.category:
                orig_resp.category_name = orig.category.name

        results.append(DuplicateComparisonItem(
            duplicate_image=dup_resp,
            original_image=orig_resp,
            similarity_percentage=round(dup.duplicate_similarity or 100.0, 1),
            duplicate_type=dup.duplicate_type or "SHA256_EXACT"
        ))

    return results


@router.post("/resolve/{image_id}")
def resolve_duplicate(
    image_id: int,
    action: str,  # KEEP_AS_DUPLICATE, FORCE_APPROVE, REJECT
    db: Session = Depends(get_db)
):
    """
    Operator action on a duplicate image. Never automatically deletes files.
    """
    img = db.query(ImageItem).filter(ImageItem.id == image_id).first()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    action = action.upper()
    if action == "FORCE_APPROVE":
        img.status = "APPROVED"
        img.is_duplicate = False
        img.review_reason = "Operator override: Manually verified distinct decoration."
    elif action == "REJECT":
        img.status = "REJECTED"
        img.rejection_reason = "Confirmed duplicate image by operator."
    elif action == "KEEP_AS_DUPLICATE":
        img.status = "DUPLICATE"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    db.commit()

    audit = AuditLog(
        action="RESOLVE_DUPLICATE",
        image_id=img.id,
        details=f"Duplicate resolved with action: {action}"
    )
    db.add(audit)
    db.commit()

    return {"success": True, "image_id": img.id, "new_status": img.status}
