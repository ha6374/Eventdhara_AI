import os
import gc
import zlib
import uuid
import zipfile
import shutil
import logging
import datetime
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


def resolve_category_from_zip_path(
    db: Session,
    member_path: str,
    cache: Optional[dict] = None
) -> Optional[int]:
    """Resolves matching category from directory path inside a ZIP archive with optional memory cache."""
    norm_path = member_path.replace("\\", "/").strip("/")
    parts = norm_path.split("/")
    if len(parts) <= 1:
        return None
    dir_path = "/".join(parts[:-1]).strip().lower()
    if not dir_path:
        return None
    if cache is not None and dir_path in cache:
        return cache[dir_path]

    from app.models.category import Category
    folder_parts = parts[:-1]
    matched_id = None
    for folder_name in reversed(folder_parts):
        cleaned = folder_name.strip()
        if not cleaned:
            continue
        matched = db.query(Category).filter(Category.name.ilike(cleaned)).first()
        if not matched:
            matched = db.query(Category).filter(Category.name.ilike(f"%{cleaned}%")).first()
        if matched:
            matched_id = matched.id
            break

    if cache is not None:
        cache[dir_path] = matched_id
    return matched_id


def cleanup_batch_memory(db: Session, batch: UploadBatch):
    """
    Safely commits pending work and expunges processed image and audit items
    from SQLAlchemy's identity map while preserving the active batch in session.
    """
    db.commit()
    for obj in list(db.identity_map.values()):
        if obj is not batch:
            db.expunge(obj)
    if "images" in batch.__dict__:
        batch.__dict__.pop("images", None)
    gc.collect()


def finalize_batch(
    db: Session,
    batch: UploadBatch,
    status: str,
    valid_count: Optional[int] = None,
    invalid_count: Optional[int] = None,
    error_message: Optional[str] = None
):
    """
    Safely re-attaches batch if needed and persists final status, counts, and timestamps to PostgreSQL.
    """
    if batch not in db:
        batch = db.merge(batch)
    batch.status = status
    if valid_count is not None:
        batch.valid_files = valid_count
    if invalid_count is not None:
        batch.invalid_files = invalid_count
    if error_message is not None:
        batch.error_message = error_message
    if status in ("COMPLETED", "FAILED"):
        batch.completed_at = datetime.datetime.utcnow()
    db.commit()


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

            # Periodic session cleanup and GC to control RAM usage while preserving active batch
            if (valid_count + invalid_count) % getattr(settings, "BATCH_GC_INTERVAL", 10) == 0:
                cleanup_batch_memory(db, batch)

        finalize_batch(db, batch, status="COMPLETED", valid_count=valid_count, invalid_count=invalid_count)
        db.expunge_all()
        gc.collect()

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

    # Stream ZIP directly to disk with upload size protection
    max_upload_bytes = getattr(settings, "MAX_UPLOAD_SIZE_MB", 500) * 1024 * 1024
    total_streamed = 0
    try:
        with open(zip_path, "wb") as buffer:
            while chunk := await file.read(2 * 1024 * 1024):  # 2MB chunks
                total_streamed += len(chunk)
                if total_streamed > max_upload_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Uploaded ZIP exceeds maximum size limit of {settings.MAX_UPLOAD_SIZE_MB} MB."
                    )
                buffer.write(chunk)
    except HTTPException as e:
        finalize_batch(db, batch, status="FAILED", error_message=e.detail)
        shutil.rmtree(temp_zip_dir, ignore_errors=True)
        shutil.rmtree(extracted_dir, ignore_errors=True)
        raise

    processor = ProcessingService(db)
    valid_count = 0
    invalid_count = 0
    processed_items = []

    try:
        if not zipfile.is_zipfile(zip_path):
            raise zipfile.BadZipFile("Uploaded file header does not match ZIP format")

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            members = zip_ref.infolist()

            # Safety Limit 1: Maximum number of archive entries
            max_files = getattr(settings, "ZIP_MAX_FILES", 1000)
            if len(members) > max_files:
                raise HTTPException(
                    status_code=400,
                    detail=f"ZIP archive contains {len(members)} entries, exceeding the maximum allowed limit of {max_files}."
                )

            # Safety Limits 2 & 3: Total uncompressed size, entry size, and ZIP bomb protection
            max_total_uncompressed = getattr(settings, "ZIP_MAX_TOTAL_UNCOMPRESSED_MB", 2048) * 1024 * 1024
            max_entry_size = getattr(settings, "ZIP_MAX_FILE_SIZE_MB", 50) * 1024 * 1024
            max_ratio = getattr(settings, "ZIP_MAX_COMPRESSION_RATIO", 100.0)

            total_uncompressed = 0
            total_compressed = 0

            for member in members:
                if member.file_size > max_entry_size:
                    raise HTTPException(
                        status_code=400,
                        detail=f"ZIP entry '{member.filename}' uncompressed size ({member.file_size / (1024 * 1024):.1f} MB) exceeds maximum allowed limit of {settings.ZIP_MAX_FILE_SIZE_MB} MB."
                    )
                total_uncompressed += member.file_size
                total_compressed += member.compress_size

            if total_uncompressed > max_total_uncompressed:
                raise HTTPException(
                    status_code=400,
                    detail=f"Total uncompressed ZIP contents ({total_uncompressed / (1024 * 1024):.1f} MB) exceed maximum allowed limit of {settings.ZIP_MAX_TOTAL_UNCOMPRESSED_MB} MB."
                )

            if total_compressed > 0 and (total_uncompressed / total_compressed) > max_ratio:
                raise HTTPException(
                    status_code=400,
                    detail=f"ZIP archive rejected: excessive compression ratio ({total_uncompressed / total_compressed:.1f}:1) detected as potential ZIP bomb."
                )

            batch.total_files = len(members)
            batch.status = "PROCESSING"
            db.commit()

            category_cache: dict = {}

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

                # Ignore macOS metadata
                if basename.startswith(".") or basename.startswith("__MACOSX"):
                    continue

                if ext not in ALLOWED_EXTENSIONS:
                    invalid_count += 1
                    continue

                # Streaming member extraction with per-entry corruption resilience
                extracted_file_path = os.path.join(extracted_dir, f"{uuid.uuid4()}{ext}")
                try:
                    with zip_ref.open(member) as source, open(extracted_file_path, "wb") as target:
                        while chunk := source.read(65536):
                            target.write(chunk)
                except (zipfile.BadZipFile, zlib.error, RuntimeError, IOError) as extract_err:
                    logger.warning("Corrupted entry encountered in ZIP '%s': %s", member.filename, extract_err)
                    invalid_count += 1
                    if os.path.exists(extracted_file_path):
                        try:
                            os.remove(extracted_file_path)
                        except Exception:
                            pass
                    continue

                try:
                    # Resolve category from explicit selection or internal ZIP directory hierarchy
                    effective_cat_id = category_id or resolve_category_from_zip_path(db, member.filename, category_cache)

                    processed_image = processor.process_image(
                        source_file_path=extracted_file_path,
                        original_filename=basename,
                        batch_id=batch_id,
                        target_category_id=effective_cat_id
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
                        try:
                            os.remove(extracted_file_path)
                        except Exception:
                            pass

                # Periodic session identity map cleanup and garbage collection while preserving active batch
                if (valid_count + invalid_count) % getattr(settings, "BATCH_GC_INTERVAL", 10) == 0:
                    cleanup_batch_memory(db, batch)

        finalize_batch(db, batch, status="COMPLETED", valid_count=valid_count, invalid_count=invalid_count)
        db.expunge_all()
        gc.collect()

    except HTTPException as e:
        logger.warning("ZIP upload rejected: %s", e.detail)
        finalize_batch(db, batch, status="FAILED", error_message=e.detail)
        raise e
    except MemoryError as e:
        logger.critical("MemoryError encountered while processing ZIP: %s", e)
        finalize_batch(db, batch, status="FAILED", error_message="Server memory limit exceeded during ZIP processing.")
        raise HTTPException(status_code=503, detail="Server memory limit reached while processing ZIP archive.")
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as e:
        logger.error("Corrupted or invalid ZIP file: %s", e)
        finalize_batch(db, batch, status="FAILED", error_message=f"Corrupted or invalid ZIP archive: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Corrupted or invalid ZIP archive: {str(e)}")
    except Exception as e:
        logger.error("Failed extracting ZIP file: %s", e)
        finalize_batch(db, batch, status="FAILED", error_message=str(e))
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
