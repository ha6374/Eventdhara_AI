import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.image import ImageItem
from app.models.metadata import ImageMetadata
from app.schemas.metadata import MetadataResponse, MetadataUpdate
from app.services.metadata_service import MetadataService

router = APIRouter()


def serialize_metadata_response(meta: ImageMetadata) -> MetadataResponse:
    inclusion = []
    faq = []
    keywords = []
    tags = []
    try:
        if meta.inclusion:
            inclusion = json.loads(meta.inclusion) if isinstance(meta.inclusion, str) else meta.inclusion
    except Exception:
        inclusion = [meta.inclusion] if meta.inclusion else []

    try:
        if meta.faq:
            faq = json.loads(meta.faq) if isinstance(meta.faq, str) else meta.faq
    except Exception:
        faq = []

    try:
        if meta.keywords:
            keywords = json.loads(meta.keywords) if isinstance(meta.keywords, str) else meta.keywords
    except Exception:
        keywords = [k.strip() for k in (meta.keywords or "").split(",") if k.strip()]

    try:
        if meta.tags:
            tags = json.loads(meta.tags) if isinstance(meta.tags, str) else meta.tags
    except Exception:
        tags = [t.strip() for t in (meta.tags or "").split(",") if t.strip()]

    return MetadataResponse(
        id=meta.id,
        image_id=meta.image_id,
        name=meta.name,
        short_description=meta.short_description,
        long_description=meta.long_description,
        inclusion=inclusion,
        faq=faq,
        note=meta.note,
        keywords=keywords,
        tags=tags,
        created_at=meta.created_at,
        updated_at=meta.updated_at,
        image_filename=meta.image.original_filename if meta.image else None,
        image_url=meta.image.storage_path if meta.image else None
    )


@router.get("/all", response_model=List[MetadataResponse])
def get_all_metadata(db: Session = Depends(get_db)):
    """Fetch all generated metadata records."""
    records = db.query(ImageMetadata).order_by(ImageMetadata.updated_at.desc()).all()
    return [serialize_metadata_response(r) for r in records]


@router.get("/{image_id}", response_model=MetadataResponse)
def get_image_metadata(image_id: int, db: Session = Depends(get_db)):
    """Fetch metadata for a specific image."""
    meta = db.query(ImageMetadata).filter(ImageMetadata.image_id == image_id).first()
    if not meta:
        raise HTTPException(status_code=404, detail="Metadata not found for this image")
    return serialize_metadata_response(meta)


@router.post("/generate/{image_id}", response_model=MetadataResponse)
def generate_metadata_endpoint(image_id: int, db: Session = Depends(get_db)):
    """Trigger AI metadata generation for an approved image."""
    service = MetadataService(db)
    meta = service.generate_for_image(image_id)
    if not meta:
        raise HTTPException(status_code=400, detail="Failed to generate metadata or image is not APPROVED.")
    return serialize_metadata_response(meta)


@router.put("/{metadata_id}", response_model=MetadataResponse)
def update_metadata_endpoint(metadata_id: int, payload: MetadataUpdate, db: Session = Depends(get_db)):
    """Manually update metadata fields in the Studio."""
    service = MetadataService(db)
    meta = service.update_metadata(metadata_id, payload)
    if not meta:
        raise HTTPException(status_code=404, detail="Metadata record not found")
    return serialize_metadata_response(meta)


@router.post("/bulk-generate")
def bulk_generate_metadata(db: Session = Depends(get_db)):
    """Bulk generate metadata for all approved images missing metadata."""
    pending_images = (
        db.query(ImageItem)
        .filter(ImageItem.status == "APPROVED", ImageItem.metadata_status != "COMPLETED")
        .all()
    )
    service = MetadataService(db)
    completed = 0
    failed = 0
    for img in pending_images:
        res = service.generate_for_image(img.id)
        if res:
            completed += 1
        else:
            failed += 1

    return {
        "success": True,
        "total_attempted": len(pending_images),
        "completed": completed,
        "failed": failed
    }
