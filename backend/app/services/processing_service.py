import os
import time
import uuid
import shutil
import logging
import json
from typing import Dict, Any, Optional, Tuple
from PIL import Image
import cv2
import numpy as np
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.image import ImageItem
from app.models.category import Category
from app.models.audit import AuditLog
from app.repositories.image_repo import ImageRepository
from app.repositories.category_repo import CategoryRepository
from app.services.duplicate_service import DuplicateService
from app.services.gemini_service import gemini_service

logger = logging.getLogger("eventdhara.processing_engine")

SUPPORTED_FORMATS = {"JPEG", "JPG", "PNG", "WEBP"}


class ProcessingService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ImageRepository(db)
        self.cat_repo = CategoryRepository(db)
        self.dup_service = DuplicateService(db)

    def compute_blur_score(self, file_path: str) -> float:
        """Computes variance of the Laplacian using OpenCV."""
        try:
            img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return 0.0
            variance = cv2.Laplacian(img, cv2.CV_64F).var()
            return float(variance)
        except Exception as e:
            logger.warning("Error computing blur score for %s: %s", file_path, e)
            return 0.0

    def detect_watermark(self, file_path: str) -> Tuple[bool, float]:
        """
        Optional Watermark Detection using OpenCV corner edge and text-density analysis.
        Inspects bottom-right, bottom-left, and bottom banner regions.
        """
        if not settings.WATERMARK_DETECTION:
            return False, 0.0

        try:
            img = cv2.imread(file_path)
            if img is None:
                return False, 0.0

            h, w = img.shape[:2]
            bottom_strip = img[int(h * 0.85):h, :]
            gray = cv2.cvtColor(bottom_strip, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 100, 200)
            edge_density = np.sum(edges > 0) / float(edges.size)
            has_watermark = edge_density > 0.12
            return has_watermark, float(edge_density)
        except Exception as e:
            logger.warning("Error detecting watermark for %s: %s", file_path, e)
            return False, 0.0

    def validate_file(self, file_path: str) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """STEP 1: File Validation (format, integrity, dimensions, size)."""
        if not os.path.exists(file_path):
            return False, "File does not exist on disk", {}

        file_size = os.path.getsize(file_path)
        min_bytes = settings.MIN_FILE_SIZE_KB * 1024
        if file_size < min_bytes:
            return False, f"File size too small ({file_size / 1024:.1f} KB, minimum required is {settings.MIN_FILE_SIZE_KB} KB)", {}

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if file_size > max_bytes:
            return False, f"File size exceeds maximum allowed ({settings.MAX_UPLOAD_SIZE_MB} MB)", {}

        try:
            with Image.open(file_path) as img:
                img_format = img.format.upper() if img.format else ""
                width, height = img.size

                if img_format not in SUPPORTED_FORMATS:
                    return False, f"Unsupported image format: {img_format}. Allowed: {', '.join(SUPPORTED_FORMATS)}", {}

                # Verify image integrity (not corrupted)
                img.verify()

            # Re-open after verify to ensure full decodability
            with Image.open(file_path) as img:
                img.load()

            if width < settings.MIN_IMAGE_WIDTH or height < settings.MIN_IMAGE_HEIGHT:
                return False, f"Image resolution too low ({width}x{height}, required min {settings.MIN_IMAGE_WIDTH}x{settings.MIN_IMAGE_HEIGHT})", {}

            return True, None, {
                "file_size": file_size,
                "width": width,
                "height": height,
                "format": img_format,
            }
        except Exception as e:
            return False, f"Corrupted or invalid image file: {str(e)}", {}

    def process_image(
        self,
        source_file_path: str,
        original_filename: str,
        batch_id: Optional[str] = None,
        target_category_id: Optional[int] = None
    ) -> ImageItem:
        """
        Executes the 5-step production pipeline:
        1. File Validation
        2. Duplicate Detection
        3. Quality Check
        4. AI Classification
        5. Final Decision
        """
        start_time = time.time()
        file_uuid = str(uuid.uuid4())
        ext = os.path.splitext(original_filename)[1].lower() or ".jpg"
        new_filename = f"{file_uuid}{ext}"

        # Safe file copy to processed storage
        dest_path = os.path.abspath(os.path.join(settings.STORAGE_ROOT, "processed", new_filename))
        shutil.copy2(source_file_path, dest_path)

        # STEP 1: VALIDATION
        is_valid, val_err, meta = self.validate_file(dest_path)
        if not is_valid:
            duration_ms = (time.time() - start_time) * 1000
            item = ImageItem(
                uuid=file_uuid,
                filename=new_filename,
                original_filename=original_filename,
                file_path=dest_path,
                storage_path=f"storage/processed/{new_filename}",
                file_size=os.path.getsize(dest_path),
                width=meta.get("width", 0),
                height=meta.get("height", 0),
                format=meta.get("format", "UNKNOWN"),
                sha256="",
                phash="",
                blur_score=0.0,
                quality_status="FAILED",
                status="REJECTED",
                rejection_reason=f"Validation failed: {val_err}",
                batch_id=batch_id,
                processing_duration_ms=duration_ms
            )
            self.db.add(item)
            self.db.commit()
            self.db.refresh(item)
            return item

        # Compute hashes
        sha256_hash = self.dup_service.compute_sha256(dest_path)
        phash_str = self.dup_service.compute_phash(dest_path)

        # STEP 2: DUPLICATE DETECTION
        is_dup, dup_origin, similarity, dup_type = self.dup_service.check_global_duplicate(sha256_hash, phash_str)

        # STEP 3: QUALITY CHECK
        blur_score = self.compute_blur_score(dest_path)
        has_watermark, wm_density = self.detect_watermark(dest_path)
        quality_passed = (blur_score >= settings.BLUR_THRESHOLD) and (not has_watermark)
        quality_status = "PASSED" if quality_passed else "FAILED"

        # STEP 4: AI CLASSIFICATION (only if not a duplicate and passes basic quality)
        ai_result = {}
        ai_confidence = 0.0
        ai_decision = "REVIEW_REQUIRED"
        assigned_category_id = target_category_id

        if not is_dup and quality_passed:
            ai_result = gemini_service.classify_image(dest_path)
            ai_confidence = float(ai_result.get("confidence", 0.0))
            ai_decision = ai_result.get("decision", "REVIEW_REQUIRED")

            # Try mapping AI category to database category if not manually provided
            if not assigned_category_id:
                sub_name = ai_result.get("matched_subcategory")
                cat_name = ai_result.get("matched_category")
                matched_db_cat = None
                if sub_name:
                    matched_db_cat = self.db.query(Category).filter(Category.name.ilike(f"%{sub_name}%")).first()
                if not matched_db_cat and cat_name:
                    matched_db_cat = self.db.query(Category).filter(Category.name.ilike(f"%{cat_name}%")).first()
                if matched_db_cat:
                    assigned_category_id = matched_db_cat.id

        # STEP 5: FINAL DECISION
        # Rules:
        # 1. Never approve an image if duplicate verification fails
        # 2. Clearly unrelated images must be rejected
        # 3. Uncertain results must go to review
        # 4. Failed quality check (too blurry) -> REJECTED or REVIEW_REQUIRED based on score
        rejection_reason = None
        review_reason = None

        if is_dup:
            final_status = "DUPLICATE"
            review_reason = f"Duplicate of image #{dup_origin.id} ({similarity:.1f}% similarity via {dup_type})"
        elif not quality_passed:
            if has_watermark:
                final_status = "REVIEW_REQUIRED"
                review_reason = f"Commercial watermark or logo overlay detected in frame (Edge Density: {wm_density:.2f})"
            elif blur_score < (settings.BLUR_THRESHOLD * 0.5):
                final_status = "REJECTED"
                rejection_reason = f"Severe image blur detected (Blur Score: {blur_score:.1f}, required >= {settings.BLUR_THRESHOLD})"
            else:
                final_status = "REVIEW_REQUIRED"
                review_reason = f"Image sharpness below standard (Blur Score: {blur_score:.1f}, minimum {settings.BLUR_THRESHOLD})"
        elif ai_decision == "REJECTED":
            final_status = "REJECTED"
            rejection_reason = ai_result.get("reason", "AI detected image is not related to event decoration.")
        elif ai_decision == "APPROVED" and ai_confidence >= settings.AI_CONFIDENCE_THRESHOLD:
            final_status = "APPROVED"
        else:
            final_status = "REVIEW_REQUIRED"
            review_reason = ai_result.get("reason", "Classification requires manual operator confirmation.")

        duration_ms = (time.time() - start_time) * 1000

        image_item = ImageItem(
            uuid=file_uuid,
            filename=new_filename,
            original_filename=original_filename,
            file_path=dest_path,
            storage_path=f"storage/processed/{new_filename}",
            file_size=meta["file_size"],
            width=meta["width"],
            height=meta["height"],
            format=meta["format"],
            sha256=sha256_hash,
            phash=phash_str,
            blur_score=blur_score,
            quality_status=quality_status,
            status=final_status,
            rejection_reason=rejection_reason,
            review_reason=review_reason,
            is_duplicate=is_dup,
            duplicate_of_id=dup_origin.id if dup_origin else None,
            duplicate_similarity=similarity if is_dup else None,
            duplicate_type=dup_type,
            ai_classification=json.dumps(ai_result) if ai_result else None,
            ai_confidence=ai_confidence if ai_result else None,
            category_id=assigned_category_id,
            metadata_status="PENDING",
            drive_status="PENDING",
            batch_id=batch_id,
            processing_duration_ms=duration_ms
        )

        self.db.add(image_item)
        self.db.commit()
        self.db.refresh(image_item)

        # Audit log
        audit = AuditLog(
            action="PROCESS_IMAGE",
            image_id=image_item.id,
            details=f"Processed '{original_filename}'. Status assigned: {final_status}."
        )
        self.db.add(audit)
        self.db.commit()

        return image_item
