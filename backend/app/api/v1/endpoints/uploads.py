import os
import uuid
import zipfile
import shutil
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.models.batch import UploadBatch
from app.schemas.upload import BatchResponse, UploadResultResponse
from app.schemas.image import ImageResponse
from app.services.processing_service import ProcessingService

logger = logging.getLogger("eventdhara.uploads_api")

router = APIRouter()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def is_safe_zip_path(target_dir: str, member_path: str) -> bool:
    """Prevent Zip Slip path traversal vulnerability."""
    target_abs = os.path.abspath(target_dir)
    dest_path = os.path.abspath(os.path.join(target_dir, member_path))
    return dest_path.startswith(target_abs + os.sep) or dest_path == target_abs


def resolve_category_from_zip_path(db: Session, member_path: str) -> Optional[int]:
    """Resolves matching category from directory path inside a ZIP archive."""
    norm_path = member_path.replace("\\", "/").strip("/")
    parts = norm_path.split("/")
    if len(parts) <= 1:
        return None
    from app.models.category import Category
    folder_parts = parts[:-1]
    for folder_name in reversed(folder_parts):
        cleaned = folder_name.strip()
        matched = db.query(Category).filter(Category.name.ilike(cleaned)).first()
        if not matched:
            matched = db.query(Category).filter(Category.name.ilike(f"%{cleaned}%")).first()
        if matched:
            return matched.id
    return None


@router.post("/images", response_model=UploadResultResponse)
async def upload_multiple_images(
    files: List[UploadFile] = File(...),
    category_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Accepts multiple or individual image files, validates, and runs them through the processing pipeline.
    """
    batch_id = str(uuid.uuid4())
    batch = UploadBatch(
        id=batch_id,
        original_name=f"Batch upload ({len(files)} files)",
        total_files=len(files),
        status="PROCESSING",
        target_category_id=category_id
    )
    db.add(batch)
    db.commit()

    processed_items = []
    valid_count = 0
    invalid_count = 0
    processor = ProcessingService(db)

    temp_batch_dir = os.path.join(settings.STORAGE_ROOT, "uploads", batch_id)
    os.makedirs(temp_batch_dir, exist_ok=True)

    try:
        for file in files:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                invalid_count += 1
                continue

            temp_dest = os.path.join(temp_batch_dir, f"{uuid.uuid4()}{ext}")
            # Stream file to disk in chunks to avoid high RAM usage
            with open(temp_dest, "wb") as buffer:
                while chunk := await file.read(1024 * 1024):  # 1MB chunk
                    buffer.write(chunk)

            # Process image through pipeline
            try:
                processed_image = processor.process_image(
                    source_file_path=temp_dest,
                    original_filename=file.filename,
                    batch_id=batch_id,
                    target_category_id=category_id
                )
                valid_count += 1
                resp = ImageResponse.model_validate(processed_image)
                if processed_image.category:
                    resp.category_name = processed_image.category.name
                processed_items.append(resp)
            except Exception as e:
                logger.error("Error processing file %s: %s", file.filename, e)
                invalid_count += 1
            finally:
                if os.path.exists(temp_dest):
                    os.remove(temp_dest)

        batch.valid_files = valid_count
        batch.invalid_files = invalid_count
        batch.status = "COMPLETED"
        db.commit()

    finally:
        if os.path.exists(temp_batch_dir):
            shutil.rmtree(temp_batch_dir, ignore_errors=True)

    return UploadResultResponse(
        batch_id=batch_id,
        total_received=len(files),
        valid_images=valid_count,
        invalid_files=invalid_count,
        processed_items=processed_items,
        message=f"Processed {valid_count} valid images successfully."
    )


@router.post("/zip", response_model=UploadResultResponse)
async def upload_zip_stream(
    file: UploadFile = File(...),
    category_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Streams and processes a ZIP file without loading it completely into RAM.
    Includes Path Traversal protection (anti-ZipSlip).
    """
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid ZIP archive.")

    batch_id = str(uuid.uuid4())
    temp_zip_dir = os.path.join(settings.STORAGE_ROOT, "uploads", f"zip_{batch_id}")
    extracted_dir = os.path.join(settings.STORAGE_ROOT, "extracted", batch_id)
    os.makedirs(temp_zip_dir, exist_ok=True)
    os.makedirs(extracted_dir, exist_ok=True)

    zip_path = os.path.join(temp_zip_dir, file.filename)

    batch = UploadBatch(
        id=batch_id,
        original_name=file.filename,
        file_path=zip_path,
        status="EXTRACTING",
        target_category_id=category_id
    )
    db.add(batch)
    db.commit()

    # Stream ZIP directly to disk
    with open(zip_path, "wb") as buffer:
        while chunk := await file.read(2 * 1024 * 1024):  # 2MB chunks
            buffer.write(chunk)

    processor = ProcessingService(db)
    valid_count = 0
    invalid_count = 0
    processed_items = []

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            members = zip_ref.infolist()
            batch.total_files = len(members)
            batch.status = "PROCESSING"
            db.commit()

            for member in members:
                # Skip directory entries
                if member.is_dir():
                    continue

                # Security: Check for path traversal / Zip Slip
                if not is_safe_zip_path(extracted_dir, member.filename):
                    logger.warning("Dangerous path traversal detected in ZIP entry: %s", member.filename)
                    invalid_count += 1
                    continue

                basename = os.path.basename(member.filename)
                ext = os.path.splitext(basename)[1].lower()

                # Ignore macOS metadata or non-images
                if basename.startswith(".") or basename.startswith("__MACOSX"):
                    continue

                if ext not in ALLOWED_EXTENSIONS:
                    invalid_count += 1
                    continue

                # Streaming member extraction
                extracted_file_path = os.path.join(extracted_dir, f"{uuid.uuid4()}{ext}")
                with zip_ref.open(member) as source, open(extracted_file_path, "wb") as target:
                    shutil.copyfileobj(source, target)

                try:
                    processed_image = processor.process_image(
                        source_file_path=extracted_file_path,
                        original_filename=basename,
                        batch_id=batch_id,
                        target_category_id=category_id
                    )
                    valid_count += 1
                    resp = ImageResponse.model_validate(processed_image)
                    if processed_image.category:
                        resp.category_name = processed_image.category.name
                    processed_items.append(resp)
                except Exception as e:
                    logger.error("Failed to process extracted image %s: %s", basename, e)
                    invalid_count += 1
                finally:
                    if os.path.exists(extracted_file_path):
                        os.remove(extracted_file_path)

        batch.valid_files = valid_count
        batch.invalid_files = invalid_count
        batch.status = "COMPLETED"
        db.commit()

    except Exception as e:
        logger.error("Failed extracting ZIP file: %s", e)
        batch.status = "FAILED"
        batch.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Error processing ZIP archive: {str(e)}")
    finally:
        shutil.rmtree(temp_zip_dir, ignore_errors=True)
        shutil.rmtree(extracted_dir, ignore_errors=True)

    return UploadResultResponse(
        batch_id=batch_id,
        total_received=valid_count + invalid_count,
        valid_images=valid_count,
        invalid_files=invalid_count,
        processed_items=processed_items,
        message=f"ZIP processed: {valid_count} images successfully evaluated."
    )


@router.get("/batches", response_model=List[BatchResponse])
def list_upload_batches(db: Session = Depends(get_db)):
    """List recent upload batches and status."""
    batches = db.query(UploadBatch).order_by(UploadBatch.created_at.desc()).limit(20).all()
    return batches
