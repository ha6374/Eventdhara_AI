from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.image import ImageItem
from app.services.drive_service import GoogleDriveService

router = APIRouter()


@router.post("/upload/{image_id}")
def upload_single_to_drive(image_id: int, db: Session = Depends(get_db)):
    """Upload an approved image to Google Drive folder structure."""
    service = GoogleDriveService(db)
    res = service.upload_approved_image(image_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Drive upload failed"))
    return res


@router.post("/bulk-upload")
def bulk_upload_to_drive(db: Session = Depends(get_db)):
    """Bulk upload all approved images to Google Drive."""
    approved_images = (
        db.query(ImageItem)
        .filter(ImageItem.status == "APPROVED", ImageItem.drive_status != "COMPLETED")
        .all()
    )
    service = GoogleDriveService(db)
    uploaded = 0
    failed = 0
    for img in approved_images:
        res = service.upload_approved_image(img.id)
        if res.get("success"):
            uploaded += 1
        else:
            failed += 1

    return {
        "success": True,
        "total_attempted": len(approved_images),
        "uploaded": uploaded,
        "failed": failed
    }


@router.post("/sync-folder/{category_id}")
def sync_category_folder(category_id: int, db: Session = Depends(get_db)):
    """Upload all approved images within a specific category and its subfolders."""
    service = GoogleDriveService(db)
    res = service.upload_category_folder(category_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Sync failed"))
    return res


@router.get("/folders")
def get_drive_folder_hierarchy(db: Session = Depends(get_db)):
    """Get full hierarchical Drive folder tree with approved/synced/pending statistics."""
    service = GoogleDriveService(db)
    return service.get_drive_folder_hierarchy()


@router.get("/status")
def get_drive_status(db: Session = Depends(get_db)):
    """Get overall Google Drive synchronization status and stats."""
    total_approved = db.query(ImageItem).filter(ImageItem.status == "APPROVED").count()
    uploaded = db.query(ImageItem).filter(ImageItem.drive_status == "COMPLETED").count()
    pending = db.query(ImageItem).filter(ImageItem.status == "APPROVED", ImageItem.drive_status != "COMPLETED").count()
    failed = db.query(ImageItem).filter(ImageItem.drive_status == "FAILED").count()

    return {
        "total_approved": total_approved,
        "synced_to_drive": uploaded,
        "pending_sync": pending,
        "failed_sync": failed,
        "drive_root": "EventDhara Decoration Images"
    }
