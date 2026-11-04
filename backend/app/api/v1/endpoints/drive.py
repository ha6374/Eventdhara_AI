from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.models.image import ImageItem
from app.services.drive_service import GoogleDriveService
from app.services.sheets_service import GoogleSheetsService

router = APIRouter()


class CreateFolderRequest(BaseModel):
    name: str
    parent_id: Optional[str] = None


class SheetsExportRequest(BaseModel):
    category_id: Optional[int] = None
    status: Optional[str] = "APPROVED"
    title_prefix: Optional[str] = "EventDhara Catalog"


@router.get("/status")
def get_drive_status(db: Session = Depends(get_db)):
    """Get overall Google Drive synchronization status, user info, and storage quotas."""
    service = GoogleDriveService(db)
    conn_info = service.get_connection_status()

    total_approved = db.query(ImageItem).filter(ImageItem.status == "APPROVED").count()
    uploaded = db.query(ImageItem).filter(ImageItem.drive_status == "COMPLETED").count()
    pending = db.query(ImageItem).filter(ImageItem.status == "APPROVED", ImageItem.drive_status != "COMPLETED").count()
    failed = db.query(ImageItem).filter(ImageItem.drive_status == "FAILED").count()

    conn_info.update({
        "total_approved": total_approved,
        "synced_to_drive": uploaded,
        "pending_sync": pending,
        "failed_sync": failed,
    })
    return conn_info


@router.get("/folders")
def get_drive_folder_hierarchy(db: Session = Depends(get_db)):
    """Get full hierarchical Drive folder tree with approved/synced/pending statistics."""
    service = GoogleDriveService(db)
    return service.get_drive_folder_hierarchy()


@router.get("/browse-folders")
def browse_drive_folders(parent_id: Optional[str] = None, db: Session = Depends(get_db)):
    """Browse live folders inside Google Drive."""
    service = GoogleDriveService(db)
    return service.list_folders(parent_id=parent_id)


@router.post("/folder")
def create_drive_folder(payload: CreateFolderRequest, db: Session = Depends(get_db)):
    """Create a new folder on Google Drive."""
    service = GoogleDriveService(db)
    res = service.create_drive_folder(name=payload.name, parent_id=payload.parent_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Folder creation failed"))
    return res


@router.post("/upload/{image_id}")
def upload_single_to_drive(image_id: int, db: Session = Depends(get_db)):
    """Upload an approved image to Google Drive category folder structure."""
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


@router.post("/disconnect")
def disconnect_drive(db: Session = Depends(get_db)):
    """Disconnect Google Drive integration."""
    service = GoogleDriveService(db)
    return service.disconnect_drive()


@router.post("/export-sheets")
def export_to_google_sheets(payload: Optional[SheetsExportRequest] = None, db: Session = Depends(get_db)):
    """
    Exports product catalog metadata and image URLs into Google Sheets.
    """
    service = GoogleSheetsService(db)
    cat_id = payload.category_id if payload else None
    status = payload.status if payload else "APPROVED"
    prefix = payload.title_prefix if payload else "EventDhara Catalog"

    res = service.export_metadata_to_sheets(category_id=cat_id, status=status, title_prefix=prefix)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Google Sheets export failed"))
    return res
