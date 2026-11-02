from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.image import ImageItem
from app.schemas.image import ImageResponse
from app.services.processing_service import ProcessingService

router = APIRouter()


@router.post("/retry/{image_id}", response_model=ImageResponse)
def retry_image_processing(image_id: int, db: Session = Depends(get_db)):
    """Re-run processing pipeline on an existing image."""
    img = db.query(ImageItem).filter(ImageItem.id == image_id).first()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    processor = ProcessingService(db)
    # Re-run pipeline on the existing file
    reprocessed = processor.process_image(
        source_file_path=img.file_path,
        original_filename=img.original_filename,
        target_category_id=img.category_id
    )
    return reprocessed


@router.get("/queue")
def get_processing_queue(db: Session = Depends(get_db)):
    """Fetch images currently in review or pending state."""
    items = (
        db.query(ImageItem)
        .filter(ImageItem.status.in_(["PENDING", "REVIEW_REQUIRED"]))
        .order_by(ImageItem.created_at.desc())
        .limit(50)
        .all()
    )
    return {
        "queue_count": len(items),
        "items": [
            {
                "id": i.id,
                "filename": i.original_filename,
                "status": i.status,
                "quality_status": i.quality_status,
                "blur_score": i.blur_score,
                "review_reason": i.review_reason,
                "created_at": i.created_at
            }
            for i in items
        ]
    }
