import json
import logging
import threading
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, Body
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.image import ImageItem
from app.models.metadata import ImageMetadata
from app.schemas.metadata import MetadataResponse, MetadataUpdate
from app.services.metadata_service import (
    MetadataService,
    MetadataError,
    MetadataNotFoundError,
    MetadataNotApprovedError,
    MetadataConcurrencyError,
    MetadataGenerationError,
)

logger = logging.getLogger("eventdhara.metadata_endpoint")

router = APIRouter()
_bulk_lock = threading.Lock()


def serialize_metadata_response(meta: ImageMetadata, message: Optional[str] = None) -> MetadataResponse:
    inclusion = []
    faq = []
    keywords = []
    tags = []
    custom_fields = {}

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

    try:
        if meta.custom_fields:
            custom_fields = json.loads(meta.custom_fields) if isinstance(meta.custom_fields, str) else meta.custom_fields
    except Exception:
        custom_fields = {}

    photo_url = None
    orig_filename = None
    cat_name = None
    status = "APPROVED"

    if meta.image:
        orig_filename = meta.image.original_filename
        cat_name = meta.image.category.name if meta.image.category else "Unassigned"
        status = meta.image.status
        photo_url = meta.image.drive_url or (
            f"https://drive.google.com/file/d/{meta.image.drive_file_id}/view"
            if meta.image.drive_file_id
            else f"/{meta.image.storage_path}"
        )

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
        custom_fields=custom_fields,
        created_at=meta.created_at,
        updated_at=meta.updated_at,
        image_filename=meta.image.filename if meta.image else None,
        original_filename=orig_filename,
        image_url=f"/{meta.image.storage_path}" if meta.image else None,
        photo=photo_url,
        category_name=cat_name,
        approval_status=status,
        processing_status="COMPLETED",
        message=message
    )


@router.get("/all", response_model=List[MetadataResponse])
def get_all_metadata(db: Session = Depends(get_db)):
    """Fetch all generated metadata records."""
    records = db.query(ImageMetadata).order_by(ImageMetadata.updated_at.desc()).all()
    return [serialize_metadata_response(r) for r in records]



@router.get("/category/{category_id}", response_model=List[MetadataResponse])
def get_category_metadata(category_id: int, db: Session = Depends(get_db)):
    """Fetch metadata records belonging to a specific category."""
    category_ids = MetadataService(db)._get_category_ids_including_descendants(category_id)

    records = (
        db.query(ImageMetadata)
        .join(ImageItem, ImageMetadata.image_id == ImageItem.id)
        .filter(ImageItem.category_id.in_(category_ids))
        .order_by(ImageMetadata.updated_at.desc())
        .all()
    )
    return [serialize_metadata_response(r) for r in records]


@router.delete("/delete/{metadata_id}")
def delete_single_metadata(metadata_id: int, db: Session = Depends(get_db)):
    """Delete one metadata record only. Original image remains safe."""
    service = MetadataService(db)

    try:
        deleted = service.delete_metadata(metadata_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Metadata record not found")

        return {
            "success": True,
            "deleted_count": 1,
            "message": "Metadata deleted successfully. Original image was preserved."
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Single metadata deletion failed")
        raise HTTPException(status_code=500, detail="Metadata deletion failed")


@router.post("/delete/bulk")
def delete_multiple_metadata(
    metadata_ids: List[int] = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """Delete selected metadata records only."""
    if not metadata_ids:
        raise HTTPException(status_code=400, detail="Select at least one metadata record")

    if any(metadata_id <= 0 for metadata_id in metadata_ids):
        raise HTTPException(status_code=400, detail="Invalid metadata ID")

    try:
        deleted_count = MetadataService(db).delete_multiple_metadata(metadata_ids)
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"{deleted_count} metadata records deleted. Original images were preserved."
        }
    except Exception:
        logger.exception("Bulk metadata deletion failed")
        raise HTTPException(status_code=500, detail="Bulk metadata deletion failed")


@router.delete("/category/{category_id}")
def delete_category_metadata(category_id: int, db: Session = Depends(get_db)):
    """Delete metadata for a category without deleting its images or category."""
    if category_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid category ID")

    try:
        deleted_count = MetadataService(db).delete_category_metadata(category_id)
        return {
            "success": True,
            "category_id": category_id,
            "deleted_count": deleted_count,
            "message": f"{deleted_count} metadata records deleted. Images and category were preserved."
        }
    except Exception:
        logger.exception("Category metadata deletion failed")
        raise HTTPException(status_code=500, detail="Category metadata deletion failed")

@router.get("/{image_id}", response_model=MetadataResponse)
def get_image_metadata(image_id: int, db: Session = Depends(get_db)):
    """Fetch metadata for a specific image."""
    meta = db.query(ImageMetadata).filter(ImageMetadata.image_id == image_id).first()
    if not meta:
        raise HTTPException(status_code=404, detail="Metadata not found for this image")
    return serialize_metadata_response(meta)


@router.post("/generate/{image_id}", response_model=MetadataResponse)
def generate_metadata_endpoint(image_id: int, response: Response, db: Session = Depends(get_db)):
    """
    Trigger AI metadata generation for an approved image.
    If metadata is already COMPLETED, skips generation and returns existing metadata.
    """
    service = MetadataService(db)
    try:
        meta, status_code = service.generate_for_image(image_id, force_regenerate=False)
        if status_code == "ALREADY_COMPLETED":
            response.headers["X-Metadata-Notice"] = "Metadata already generated"
            return serialize_metadata_response(meta, message="Metadata already generated")
        else:
            return serialize_metadata_response(meta, message="Metadata generated successfully")
    except MetadataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except MetadataNotApprovedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except MetadataConcurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except MetadataGenerationError as e:
        err_msg = str(e)
        status_code = 502 if any(q in err_msg.lower() for q in ["429", "quota", "resource_exhausted"]) else 400
        raise HTTPException(status_code=status_code, detail=err_msg)
    except Exception as e:
        logger.error("Unexpected error generating metadata for image #%s: %s", image_id, e)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.post("/regenerate/{image_id}", response_model=MetadataResponse)
def regenerate_metadata_endpoint(image_id: int, db: Session = Depends(get_db)):
    """
    Force regenerate AI metadata for an approved image.
    Generates fresh metadata from the original image and replaces existing metadata
    only after Gemini returns valid structured metadata.
    If Gemini fails, old metadata is preserved.
    """
    service = MetadataService(db)
    try:
        meta, status_code = service.generate_for_image(image_id, force_regenerate=True)
        return serialize_metadata_response(meta, message="Metadata regenerated successfully")
    except MetadataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except MetadataNotApprovedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except MetadataConcurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except MetadataGenerationError as e:
        err_msg = str(e)
        status_code = 502 if any(q in err_msg.lower() for q in ["429", "quota", "resource_exhausted"]) else 400
        raise HTTPException(status_code=status_code, detail=f"Regeneration failed: {err_msg}. Existing metadata was preserved.")
    except Exception as e:
        logger.error("Unexpected error regenerating metadata for image #%s: %s", image_id, e)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


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
    """
    Bulk generate metadata for approved images.
    - Processes only APPROVED images.
    - Skips COMPLETED and PROCESSING images.
    - Retries FAILED and PENDING images.
    - Never processes the same image twice.
    - Prevents concurrent bulk jobs.
    - Handles 429 quota errors by stopping loop and returning remaining count.
    - Returns accurate progress counts: total, completed, failed, skipped, remaining.
    """
    if not _bulk_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="A bulk metadata generation job is already in progress. Please wait for it to complete."
        )

    try:
        approved_images = db.query(ImageItem).filter(ImageItem.status == "APPROVED").all()

        total = len(approved_images)
        completed = 0
        failed = 0
        skipped = 0
        remaining = 0

        # Filter candidates and count skipped
        candidate_ids = []
        for img in approved_images:
            if img.metadata_status == "COMPLETED" and img.metadata_rel is not None:
                skipped += 1
            elif img.metadata_status == "PROCESSING":
                skipped += 1
            elif img.metadata_status in ("PENDING", "FAILED") or (img.metadata_rel is None):
                candidate_ids.append(img.id)
            else:
                skipped += 1

        # Deduplicate candidate IDs
        candidate_ids = list(dict.fromkeys(candidate_ids))

        service = MetadataService(db)
        quota_exceeded = False

        for idx, img_id in enumerate(candidate_ids):
            if quota_exceeded:
                remaining += 1
                continue

            try:
                meta, status_code = service.generate_for_image(img_id, force_regenerate=False)
                if status_code == "ALREADY_COMPLETED":
                    skipped += 1
                else:
                    completed += 1
            except MetadataConcurrencyError:
                skipped += 1
            except MetadataGenerationError as gen_err:
                failed += 1
                err_text = str(gen_err).lower()
                if "429" in err_text or "quota" in err_text or "resource_exhausted" in err_text:
                    logger.error("Gemini API rate/quota limit encountered on image #%s. Halting remaining bulk tasks.", img_id)
                    quota_exceeded = True
            except Exception as e:
                logger.error("Bulk metadata generation error on image #%s: %s", img_id, e)
                failed += 1

        return {
            "success": True,
            "total": total,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
            "remaining": remaining,
            "message": (
                "Bulk metadata generation complete."
                if not quota_exceeded
                else "Bulk generation stopped due to Gemini API rate/quota limits. Remaining images were not attempted."
            )
        }
    finally:
        _bulk_lock.release()
