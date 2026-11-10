import os
import math
import mimetypes
import shutil
import zipfile
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models.image import ImageItem
from app.models.audit import AuditLog
from app.models.feedback import RejectionFeedback
from app.schemas.image import (
    ImageResponse,
    ImageListResponse,
    ImageStatusUpdate,
    ImageBulkAction,
    ImageRejectRequest,
    FeedbackResponse
)
from app.repositories.image_repo import ImageRepository
from app.services.duplicate_service import DuplicateService
from app.services.metadata_service import MetadataService
from app.services.drive_service import GoogleDriveService
from app.services.feedback_service import FeedbackLearningService
from app.services.category_storage import (
    organize_image_in_category_folder,
    remove_image_from_storage
)

router = APIRouter()


@router.get("/", response_model=ImageListResponse)
def list_images(
    status: Optional[str] = None,
    category_id: Optional[int] = None,
    quality_status: Optional[str] = None,
    is_duplicate: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(24, ge=1, le=200),
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
        resp.file_url = f"/api/v1/images/{img.id}/file"
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


@router.get("/feedbacks", response_model=List[FeedbackResponse])
def get_all_feedbacks(db: Session = Depends(get_db)):
    """Retrieve recorded operator rejection feedback history."""
    feedbacks = db.query(RejectionFeedback).order_by(RejectionFeedback.created_at.desc()).limit(100).all()
    return feedbacks


@router.get("/evaluation")
def get_model_evaluation(db: Session = Depends(get_db)):
    """Retrieve AI model evaluation metrics (Precision, Recall, Accuracy, F1-Score)."""
    feedback_service = FeedbackLearningService(db)
    return feedback_service.evaluate_model_performance()


@router.get("/{image_id}", response_model=ImageResponse)
def get_image(image_id: int, db: Session = Depends(get_db)):
    """Fetch detailed image record."""
    repo = ImageRepository(db)
    img = repo.get_by_id(image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    resp = ImageResponse.model_validate(img)
    resp.file_url = f"/api/v1/images/{img.id}/file"
    if img.category:
        resp.category_name = img.category.name
    return resp


def find_physical_image_file(img: ImageItem) -> Optional[str]:
    """Locates physical image file across all storage locations and backups."""
    # 1. Direct file_path from DB
    if img.file_path and os.path.exists(img.file_path) and os.path.isfile(img.file_path):
        return os.path.abspath(img.file_path)

    filename = img.filename
    orig_filename = img.original_filename
    uuid_str = img.uuid or ""
    uuid_prefix = uuid_str[:8] if uuid_str else ""

    # Candidate storage roots to check
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    candidate_roots = [
        os.path.abspath(settings.STORAGE_ROOT),
        os.path.abspath(os.path.join(project_root, "storage")),
        os.path.abspath(os.path.join(project_root, "..", "storage")),
        os.path.abspath(os.path.join(os.path.expanduser("~"), "storage")),
    ]
    seen = set()
    candidate_roots = [r for r in candidate_roots if r and not (r in seen or seen.add(r)) and os.path.exists(r)]

    # 2. Check candidate storage directories
    for root_dir in candidate_roots:
        # Check root/processed/filename
        proc_path = os.path.join(root_dir, "processed", filename)
        if os.path.isfile(proc_path):
            return os.path.abspath(proc_path)

        # Check root/relative storage_path
        if img.storage_path:
            clean_rel = img.storage_path.replace("storage/", "").replace("storage\\\\", "").replace("storage\\", "").lstrip("/\\\\").lstrip("/\\")
            rel_candidate = os.path.join(root_dir, clean_rel)
            if os.path.isfile(rel_candidate):
                return os.path.abspath(rel_candidate)

        # Check direct root/filename
        direct_path = os.path.join(root_dir, filename)
        if os.path.isfile(direct_path):
            return os.path.abspath(direct_path)

        # Search category and pipeline directories
        for subfolder_name in ["EventDhara", "approved", "rejected", "duplicates", "uploads", "extracted"]:
            subfolder = os.path.join(root_dir, subfolder_name)
            if os.path.exists(subfolder):
                for walk_root, _, files in os.walk(subfolder):
                    for f in files:
                        if f == filename or f == orig_filename or (uuid_prefix and uuid_prefix in f):
                            matched = os.path.join(walk_root, f)
                            if os.path.isfile(matched):
                                return os.path.abspath(matched)

    # 3. Check local download / backup folders for original copy
    backup_locations = [
        os.path.join(os.path.expanduser("~"), "Downloads", "pastelcolorbabyshower"),
        os.path.join(os.path.expanduser("~"), "Downloads"),
    ]
    for bloc in backup_locations:
        if os.path.exists(bloc) and orig_filename:
            target = os.path.join(bloc, orig_filename)
            if os.path.isfile(target):
                try:
                    dest_proc = os.path.join(settings.STORAGE_ROOT, "processed", filename)
                    os.makedirs(os.path.dirname(dest_proc), exist_ok=True)
                    shutil.copy2(target, dest_proc)
                    return os.path.abspath(dest_proc)
                except Exception:
                    return os.path.abspath(target)

    # 4. Check known zip archives in Downloads
    downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    if os.path.exists(downloads_dir) and orig_filename:
        for zname in ["pastelcolorbabyshower.zip", "pinterest-pins-2026-11-01 (1).zip"]:
            zpath = os.path.join(downloads_dir, zname)
            if os.path.isfile(zpath):
                try:
                    with zipfile.ZipFile(zpath, "r") as zf:
                        if orig_filename in zf.namelist():
                            data = zf.read(orig_filename)
                            dest_proc = os.path.join(settings.STORAGE_ROOT, "processed", filename)
                            os.makedirs(os.path.dirname(dest_proc), exist_ok=True)
                            with open(dest_proc, "wb") as f_out:
                                f_out.write(data)
                            return os.path.abspath(dest_proc)
                except Exception:
                    pass

    return None

def generate_placeholder_svg(title: str, reason: str = "Asset Missing on Disk (Storage Reset)") -> str:
    escaped_title = (title or "Decoration Image").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    escaped_reason = (reason or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400" fill="none">
  <rect width="600" height="400" fill="#0F172A"/>
  <rect x="20" y="20" width="560" height="360" rx="12" fill="#1E293B" stroke="#334155" stroke-dasharray="6 6"/>
  <circle cx="300" cy="155" r="44" fill="#334155"/>
  <path d="M282 171L294 153L304 163L316 143L328 171H282Z" fill="#94A3B8"/>
  <circle cx="316" cy="139" r="5" fill="#F59E0B"/>
  <text x="300" y="235" font-family="system-ui, -apple-system, sans-serif" font-size="15" font-weight="600" fill="#F1F5F9" text-anchor="middle">{escaped_title[:45]}</text>
  <text x="300" y="260" font-family="system-ui, -apple-system, sans-serif" font-size="12" fill="#94A3B8" text-anchor="middle">{escaped_reason}</text>
  <rect x="200" y="285" width="200" height="26" rx="13" fill="#B45309" fill-opacity="0.2" stroke="#F59E0B" stroke-width="1"/>
  <text x="300" y="302" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="500" fill="#FBBF24" text-anchor="middle">Render Persistent Disk Required</text>
</svg>"""


@router.get("/{image_id}/file")
def get_image_file(
    image_id: int,
    fallback: bool = Query(False, description="Return placeholder SVG if file missing on disk"),
    db: Session = Depends(get_db)
):
    """
    Serves the actual binary image bytes with the correct MIME type.
    1. Checks local storage.
    2. If locally missing (e.g., container restart), serves from PostgreSQL backup and reconstructs disk file.
    3. If not in DB backup, fetches image bytes from private Google Drive via authenticated Drive API.
    4. Never redirects to webViewLink or public URLs; keeps Drive assets private.
    """
    repo = ImageRepository(db)
    img = repo.get_by_id(image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image record not found")

    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif"
    }

    # 1. Serve local image when physically available on disk
    file_path = find_physical_image_file(img)
    if file_path and os.path.isfile(file_path):
        ext = os.path.splitext(file_path)[1].lower()
        mime_type = mime_map.get(ext) or mimetypes.guess_type(file_path)[0] or "image/jpeg"
        return FileResponse(
            path=file_path,
            media_type=mime_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "X-Image-Source": "local-disk",
                "X-Image-Id": str(img.id),
                "Content-Disposition": f'inline; filename="{img.original_filename}"'
            }
        )

    # 2. Reconstruct from PostgreSQL backup if local file was wiped
    if img.drive_backup_data:
        ext = os.path.splitext(img.filename or img.original_filename)[1].lower()
        mime_type = mime_map.get(ext) or "image/jpeg"

        # Reconstruct file locally on disk for fast subsequent accesses
        try:
            target_path = img.file_path or os.path.abspath(os.path.join(settings.STORAGE_ROOT, "processed", img.filename))
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "wb") as bf:
                bf.write(img.drive_backup_data)
            img.file_path = target_path
            db.commit()
        except Exception as write_err:
            pass

        return Response(
            content=img.drive_backup_data,
            media_type=mime_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "X-Image-Source": "database-backup",
                "X-Image-Id": str(img.id),
                "Content-Disposition": f'inline; filename="{img.original_filename}"'
            }
        )

    # 3. Fetch from private Google Drive using authenticated API (no webViewLink redirects)
    if img.drive_file_id:
        try:
            drive_svc = GoogleDriveService(db)
            drive_bytes, drive_mime = drive_svc.download_image_bytes(img.drive_file_id)
            if drive_bytes:
                actual_mime = drive_mime or mime_map.get(os.path.splitext(img.original_filename)[1].lower()) or "image/jpeg"

                # Reconstruct/cache file on disk for future fast access
                try:
                    target_path = img.file_path or os.path.abspath(os.path.join(settings.STORAGE_ROOT, "processed", img.filename))
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with open(target_path, "wb") as bf:
                        bf.write(drive_bytes)
                    img.file_path = target_path
                    db.commit()
                except Exception:
                    pass

                return Response(
                    content=drive_bytes,
                    media_type=actual_mime,
                    headers={
                        "Cache-Control": "public, max-age=86400",
                        "X-Image-Source": "google-drive-authenticated",
                        "X-Image-Id": str(img.id),
                        "Content-Disposition": f'inline; filename="{img.original_filename}"'
                    }
                )
        except Exception as drive_fetch_err:
            pass

    # 4. If fallback requested, return SVG placeholder
    if fallback:
        svg_content = generate_placeholder_svg(img.original_filename)
        return Response(
            content=svg_content,
            media_type="image/svg+xml",
            headers={"Cache-Control": "no-cache", "X-Image-Missing": "true"}
        )

    raise HTTPException(
        status_code=404,
        detail=f"Image #{image_id} '{img.original_filename}' is not physically present on disk or cloud storage.",
        headers={"X-Image-Missing": "true"}
    )

@router.get("/{image_id}/placeholder")
def get_image_placeholder(image_id: int, db: Session = Depends(get_db)):
    """Returns an SVG placeholder image for missing or failed images."""
    repo = ImageRepository(db)
    img = repo.get_by_id(image_id)
    title = img.original_filename if img else f"Image #{image_id}"
    svg_content = generate_placeholder_svg(title)
    return Response(
        content=svg_content,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600", "X-Image-Missing": "true"}
    )


@router.delete("/{image_id}")
def delete_image(image_id: int, db: Session = Depends(get_db)):
    """
    Permanently deletes a single image from the database and storage folders,
    logging the deletion action in audit logs.
    """
    repo = ImageRepository(db)
    img = repo.get_by_id(image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    filename = img.original_filename
    cat_name = img.category.name if img.category else "Uncategorized"

    # Audit log entry before deletion
    audit = AuditLog(
        action="DELETE_IMAGE",
        image_id=image_id,
        details=f"Permanently deleted image #{image_id} ('{filename}') from category '{cat_name}'."
    )
    db.add(audit)
    db.commit()

    success = repo.delete(image_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete image files")

    return {
        "success": True,
        "image_id": image_id,
        "filename": filename,
        "message": f"Image #{image_id} successfully deleted."
    }


@router.post("/{image_id}/reject", response_model=ImageResponse)
def reject_image_with_feedback(
    image_id: int,
    payload: ImageRejectRequest,
    db: Session = Depends(get_db)
):
    """
    Rejects an image and collects structured rejection feedback to improve future AI classifications.
    """
    repo = ImageRepository(db)
    img = repo.get_by_id(image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    old_status = img.status
    img.status = "REJECTED"
    img.rejection_reason = payload.rejection_reason
    db.commit()

    # Record feedback and trigger AI learning
    try:
        feedback_service = FeedbackLearningService(db)
        feedback_service.record_feedback(
            image_id=img.id,
            rejection_reason=payload.rejection_reason,
            custom_feedback=payload.custom_feedback,
            user_id=payload.user_id or "operator"
        )
    except Exception as e:
        logger = logging.getLogger("eventdhara.images")
        logger.warning("Error recording rejection feedback: %s", e)

    # Relocate file to category Rejected folder
    try:
        organize_image_in_category_folder(img, old_status=old_status)
    except Exception as e:
        logger = logging.getLogger("eventdhara.images")
        logger.warning("Error reorganizing category folder on reject: %s", e)

    # Audit log
    audit = AuditLog(
        action="REJECT_IMAGE",
        image_id=img.id,
        details=f"Image rejected. Reason: '{payload.rejection_reason}'. Feedback: '{payload.custom_feedback or ''}'"
    )
    db.add(audit)
    db.commit()
    db.refresh(img)

    resp = ImageResponse.model_validate(img)
    resp.file_url = f"/api/v1/images/{img.id}/file"
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

    # Relocate file in category folders
    try:
        organize_image_in_category_folder(img, old_status=old_status)
    except Exception as e:
        pass

    # If rejected, record feedback
    if new_status == "REJECTED":
        try:
            feedback_service = FeedbackLearningService(db)
            feedback_service.record_feedback(
                image_id=img.id,
                rejection_reason=payload.reason or "Manual Operator Rejection",
                custom_feedback=payload.custom_feedback
            )
        except Exception:
            pass

    # Audit log
    audit = AuditLog(
        action="UPDATE_STATUS",
        image_id=img.id,
        details=f"Status changed from {old_status} to {new_status}. Reason: {payload.reason or 'Manual review action'}"
    )
    db.add(audit)
    db.commit()

    # Automatic Google Drive upload after approval
    if new_status == "APPROVED":
        approved_image_id = img.id
        try:
            drive_service = GoogleDriveService(db)
            drive_service.upload_approved_image(approved_image_id)
        except Exception as drive_error:
            print(f"Google Drive upload failed: {drive_error}")

        img = db.query(ImageItem).populate_existing().filter(
            ImageItem.id == approved_image_id
        ).first()

        if img is None:
            raise HTTPException(status_code=404, detail="Image not found")
    resp = ImageResponse.model_validate(img)
    resp.file_url = f"/api/v1/images/{img.id}/file"
    if img.category:
        resp.category_name = img.category.name
    return resp


@router.post("/bulk-action")
def bulk_image_action(payload: ImageBulkAction, db: Session = Depends(get_db)):
    """
    Execute bulk batch actions across multiple selected images (including DELETE).
    """
    action = payload.action.upper()
    images = db.query(ImageItem).filter(ImageItem.id.in_(payload.image_ids)).all()
    dup_service = DuplicateService(db)
    meta_service = MetadataService(db)
    drive_service = GoogleDriveService(db)
    repo = ImageRepository(db)

    success_count = 0
    failed_count = 0
    messages = []

    for img in images:
        try:
            if action == "DELETE":
                success = repo.delete(img.id)
                if success:
                    success_count += 1
                else:
                    failed_count += 1
            elif action == "APPROVE":
                # Recheck duplicate status
                is_dup, orig, sim, _ = dup_service.check_global_duplicate(
                    img.sha256, img.phash, exclude_id=img.id
                )
                if is_dup:
                    failed_count += 1
                    messages.append(f"Image #{img.id} is duplicate of #{orig.id}")
                    continue

                old_status = img.status
                img.status = "APPROVED"
                organize_image_in_category_folder(img, old_status=old_status)

                # Commit approval independently of Drive upload.
                db.commit()
                success_count += 1

                # Automatically upload approved image to Google Drive.
                try:
                    upload_result = drive_service.upload_approved_image(img.id)

                    if not upload_result.get("success"):
                        messages.append(
                            f"Image #{img.id} approved, but Drive upload failed: "
                            f"{upload_result.get('message', 'Unknown error')}"
                        )

                except Exception as drive_error:
                    db.rollback()

                    approved_img = db.query(ImageItem).filter(
                        ImageItem.id == img.id
                    ).first()

                    if approved_img:
                        approved_img.drive_status = "FAILED"
                        db.commit()

                    messages.append(
                        f"Image #{img.id} approved, but Drive upload failed: "
                        f"{str(drive_error)}"
                    )
            elif action == "REJECT":
                old_status = img.status
                img.status = "REJECTED"
                img.rejection_reason = payload.reason or "Bulk rejected by operator"
                organize_image_in_category_folder(img, old_status=old_status)
                # Record feedback
                try:
                    fservice = FeedbackLearningService(db)
                    fservice.record_feedback(image_id=img.id, rejection_reason=img.rejection_reason)
                except Exception:
                    pass
                success_count += 1
            elif action == "MARK_REVIEW":
                old_status = img.status
                img.status = "REVIEW_REQUIRED"
                img.review_reason = payload.reason or "Marked for review in bulk"
                organize_image_in_category_folder(img, old_status=old_status)
                success_count += 1
            elif action == "ASSIGN_CATEGORY":
                if payload.category_id:
                    img.category_id = payload.category_id
                    organize_image_in_category_folder(img)
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
