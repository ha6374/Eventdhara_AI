import os
import time
import uuid
import shutil
import logging
import json
import datetime
from typing import Dict, Any, Optional, Tuple
from PIL import Image
import cv2
import numpy as np

# Restrict OpenCV to single-threaded execution to prevent thread pool memory overhead and fragmentation on Render
try:
    cv2.setNumThreads(1)
except Exception:
    pass

from sqlalchemy.orm import Session
from app.core.config import settings

# Configure PIL decompression bomb protection from settings
Image.MAX_IMAGE_PIXELS = getattr(settings, "MAX_IMAGE_PIXELS", 60_000_000)
from app.models.image import ImageItem
from app.models.category import Category
from app.models.audit import AuditLog
from app.repositories.image_repo import ImageRepository
from app.repositories.category_repo import CategoryRepository
from app.services.duplicate_service import DuplicateService
from app.services.gemini_service import gemini_service
from app.services.feedback_service import FeedbackLearningService
from app.services.category_storage import organize_image_in_category_folder

logger = logging.getLogger("eventdhara.processing_engine")

SUPPORTED_FORMATS = {"JPEG", "JPG", "PNG", "WEBP"}


class ProcessingService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ImageRepository(db)
        self.cat_repo = CategoryRepository(db)
        self.dup_service = DuplicateService(db)
        self.feedback_service = FeedbackLearningService(db)

    def _load_optimized_grayscale(self, file_path: str) -> Optional[np.ndarray]:
        """Loads image as grayscale with controlled max dimension to prevent memory blowups."""
        try:
            img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return None
            h, w = img.shape[:2]
            max_dim = max(h, w)
            max_allowed = getattr(settings, "OPENCV_MAX_PROCESSING_DIMENSION", 1920)
            if max_dim > max_allowed:
                scale = max_allowed / float(max_dim)
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                del img
                return resized
            return img
        except Exception as e:
            logger.warning("Failed loading grayscale image for %s: %s", file_path, e)
            return None

    def compute_blur_score(self, file_path: str, preloaded_gray: Optional[np.ndarray] = None) -> float:
        """Computes variance of the Laplacian using OpenCV with memory-optimized CV_32F."""
        img = None
        should_del = False
        try:
            if preloaded_gray is not None:
                img = preloaded_gray
            else:
                img = self._load_optimized_grayscale(file_path)
                should_del = True

            if img is None or img.size == 0:
                return 0.0

            laplacian = cv2.Laplacian(img, cv2.CV_32F)
            variance = float(laplacian.var())
            del laplacian
            return variance
        except Exception as e:
            logger.warning("Error computing blur score for %s: %s", file_path, e)
            return 0.0
        finally:
            if should_del and img is not None:
                del img

    def check_lighting_quality(self, file_path: str, preloaded_gray: Optional[np.ndarray] = None) -> Tuple[bool, Optional[str], float]:
        """
        Detects underexposed (dark) or overexposed (blown out) photography.
        Returns (is_acceptable, rejection_or_review_reason, mean_brightness).
        """
        img = None
        should_del = False
        try:
            if preloaded_gray is not None:
                img = preloaded_gray
            else:
                img = self._load_optimized_grayscale(file_path)
                should_del = True

            if img is None or img.size == 0:
                return True, None, 128.0

            mean_val = float(np.mean(img))
            if mean_val < 32.0:
                return False, f"Severe underexposure / dark image detected (Mean Luminance: {mean_val:.1f}/255)", mean_val
            if mean_val > 238.0:
                return False, f"Severe overexposure / blown out lighting detected (Mean Luminance: {mean_val:.1f}/255)", mean_val
            return True, None, mean_val
        except Exception as e:
            logger.warning("Error checking lighting for %s: %s", file_path, e)
            return True, None, 128.0
        finally:
            if should_del and img is not None:
                del img

    def detect_screenshot(self, file_path: str, width: int, height: int) -> Tuple[bool, float]:
        """
        Detects smartphone screenshots based on typical aspect ratios and top status bar characteristics.
        """
        if width == 0 or height == 0:
            return False, 1.0

        aspect_ratio = max(width, height) / float(min(width, height))
        # Modern mobile screenshots usually have aspect ratio > 2.05 (e.g. 19.5:9, 20:9, 21:9)
        if aspect_ratio >= 2.08:
            return True, aspect_ratio

        return False, aspect_ratio

    def detect_watermark(self, file_path: str, preloaded_gray: Optional[np.ndarray] = None) -> Tuple[bool, float]:
        """
        Inspects bottom banner and corner regions for edge density indicating watermarks/overlays.
        Loads grayscale directly to avoid full-resolution 3-channel BGR allocation.
        """
        img = None
        should_del = False
        try:
            if preloaded_gray is not None:
                img = preloaded_gray
            else:
                img = self._load_optimized_grayscale(file_path)
                should_del = True

            if img is None or img.size == 0:
                return False, 0.0

            h, w = img.shape[:2]
            bottom_strip = img[int(h * 0.85):h, :]
            edges = cv2.Canny(bottom_strip, 100, 200)
            edge_density = np.sum(edges > 0) / float(edges.size)
            del edges
            has_watermark = edge_density > 0.12
            return has_watermark, float(edge_density)
        except Exception as e:
            logger.warning("Error detecting watermark for %s: %s", file_path, e)
            return False, 0.0
        finally:
            if should_del and img is not None:
                del img

    def validate_file(self, file_path: str) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """STEP 1: File Validation (format, integrity, dimensions, size, pixel limits)."""
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

                # Check max dimensions to prevent memory exhaustion
                max_w = getattr(settings, "MAX_IMAGE_WIDTH", 12000)
                max_h = getattr(settings, "MAX_IMAGE_HEIGHT", 12000)
                if width > max_w or height > max_h:
                    return False, f"Image dimensions ({width}x{height}) exceed maximum allowed limit ({max_w}x{max_h})", {}

                total_pixels = width * height
                max_pixels = getattr(settings, "MAX_IMAGE_PIXELS", 60_000_000)
                if total_pixels > max_pixels:
                    return False, f"Image pixel count ({total_pixels:,}) exceeds maximum limit ({max_pixels:,})", {}

                # Verify image integrity (not corrupted)
                img.verify()

            # Re-open after verify to ensure decodability without keeping unneeded pixel buffers in RAM
            with Image.open(file_path) as img:
                img.draft(None, (min(width, 1000), min(height, 1000)))
                img.load()

            if width < settings.MIN_IMAGE_WIDTH or height < settings.MIN_IMAGE_HEIGHT:
                return False, f"Image resolution too low ({width}x{height}, required min {settings.MIN_IMAGE_WIDTH}x{settings.MIN_IMAGE_HEIGHT})", {}

            return True, None, {
                "file_size": file_size,
                "width": width,
                "height": height,
                "format": img_format,
            }
        except Image.DecompressionBombError as e:
            return False, f"Image rejected as potential decompression bomb: {str(e)}", {}
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
        Executes the full production pipeline:
        1. File Validation
        2. Duplicate Detection (SHA256 & pHash)
        3. Quality Check (Blur, Lighting, Watermark, Screenshot)
        4. Category-Aware AI Classification & Feedback Learning
        5. Final Decision & Category Folder Organization
        """
        start_time = time.time()
        file_uuid = str(uuid.uuid4())
        ext = os.path.splitext(original_filename)[1].lower() or ".jpg"
        new_filename = f"{file_uuid}{ext}"

        # Safe file copy to processed storage (canonical master repository)
        dest_path = os.path.abspath(os.path.join(settings.STORAGE_ROOT, "processed", new_filename))
        shutil.copy2(source_file_path, dest_path)

        # Snapshot file bytes for PostgreSQL backup to guarantee durability across container restarts
        backup_bytes = None
        try:
            with open(dest_path, "rb") as bf:
                backup_bytes = bf.read()
        except Exception as err:
            logger.warning("Could not read backup bytes for %s: %s", dest_path, err)

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
                category_id=target_category_id,
                batch_id=batch_id,
                processing_duration_ms=duration_ms,
                drive_status="PENDING",
                drive_backup_data=backup_bytes,
                drive_retry_count=0,
                drive_next_retry_at=datetime.datetime.utcnow()
            )
            self.db.add(item)
            self.db.commit()
            self.db.refresh(item)
            # Organize into Rejected folder
            organize_image_in_category_folder(item)
            try:
                from app.services.drive_worker import trigger_drive_sync
                trigger_drive_sync()
            except Exception:
                pass
            return item

        # Compute cryptographic and perceptual hashes
        sha256_hash = self.dup_service.compute_sha256(dest_path)
        phash_str = self.dup_service.compute_phash(dest_path)

        # STEP 2: DUPLICATE DETECTION
        is_dup, dup_origin, similarity, dup_type = self.dup_service.check_global_duplicate(sha256_hash, phash_str)

        # STEP 3: QUALITY & PHYSICAL CHECKS
        shared_gray = self._load_optimized_grayscale(dest_path)
        try:
            blur_score = self.compute_blur_score(dest_path, preloaded_gray=shared_gray)
            has_watermark, wm_density = self.detect_watermark(dest_path, preloaded_gray=shared_gray)
            lighting_ok, lighting_err, mean_lum = self.check_lighting_quality(dest_path, preloaded_gray=shared_gray)
        finally:
            if shared_gray is not None:
                del shared_gray
        is_screenshot, aspect_ratio = self.detect_screenshot(dest_path, meta["width"], meta["height"])

        quality_passed = (blur_score >= settings.BLUR_THRESHOLD) and (not has_watermark) and lighting_ok and (not is_screenshot)
        quality_status = "PASSED" if quality_passed else "FAILED"

        # Resolve target category
        target_category = None
        if target_category_id:
            target_category = self.db.query(Category).filter(Category.id == target_category_id).first()
        target_cat_name = target_category.name if target_category else "Unspecified"

        # STEP 4: AI CLASSIFICATION (with Historical Feedback Context Injection)
        ai_result = {}
        ai_confidence = 0.0
        ai_decision = "REVIEW_REQUIRED"
        assigned_category_id = target_category_id

        if not is_dup:
            feedback_context = self.feedback_service.get_historical_context(target_cat_name)
            ai_result = gemini_service.classify_image(
                image_path=dest_path,
                uploaded_category=target_cat_name,
                historical_feedback_context=feedback_context
            )
            ai_confidence = float(ai_result.get("confidence_score") or ai_result.get("confidence", 0.0))
            ai_decision = ai_result.get("approval_status") or ai_result.get("decision", "REVIEW_REQUIRED")

            # Try mapping AI predicted category if target wasn't explicitly selected
            if not assigned_category_id:
                pred_name = ai_result.get("predicted_category")
                sub_name = ai_result.get("matched_subcategory")
                matched_db_cat = None
                if sub_name:
                    matched_db_cat = self.db.query(Category).filter(Category.name.ilike(f"%{sub_name}%")).first()
                if not matched_db_cat and pred_name:
                    matched_db_cat = self.db.query(Category).filter(Category.name.ilike(f"%{pred_name}%")).first()
                if matched_db_cat:
                    assigned_category_id = matched_db_cat.id

        # STEP 5: FINAL DECISION POLICY
        rejection_reason = None
        review_reason = None

        if is_dup:
            final_status = "DUPLICATE"
            review_reason = f"Duplicate of image #{dup_origin.id} ({similarity:.1f}% similarity via {dup_type})"
        elif not lighting_ok:
            final_status = "REJECTED"
            rejection_reason = lighting_err
        elif is_screenshot:
            final_status = "REJECTED"
            rejection_reason = f"Detected screenshot / non-original photographic aspect ratio ({aspect_ratio:.2f}:1)"
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
        elif ai_result.get("category_match") is False:
            final_status = "REJECTED"
            rejection_reason = ai_result.get("rejection_reason") or f"Category mismatch: Image does not match selected '{target_cat_name}' category."
        elif ai_decision == "REJECTED":
            final_status = "REJECTED"
            rejection_reason = ai_result.get("rejection_reason") or "AI identified image as unrelated to event decoration."
        elif ai_decision == "APPROVED" and ai_confidence >= settings.AI_CONFIDENCE_THRESHOLD:
            final_status = "APPROVED"
        else:
            final_status = "REVIEW_REQUIRED"
            review_reason = ai_result.get("rejection_reason") or "Classification requires manual operator confirmation."

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
            drive_backup_data=backup_bytes,
            drive_retry_count=0,
            drive_next_retry_at=datetime.datetime.utcnow(),
            batch_id=batch_id,
            processing_duration_ms=duration_ms
        )

        self.db.add(image_item)
        self.db.commit()
        self.db.refresh(image_item)

        # STEP 6: DYNAMIC CATEGORY FOLDER STORAGE
        try:
            organize_image_in_category_folder(image_item)
        except Exception as e:
            logger.warning("Error organizing image in category folder: %s", e)

        # Trigger background Drive synchronization worker
        try:
            from app.services.drive_worker import trigger_drive_sync
            trigger_drive_sync()
        except Exception:
            pass

        # Audit log
        audit = AuditLog(
            action="PROCESS_IMAGE",
            image_id=image_item.id,
            details=f"Processed '{original_filename}'. Status assigned: {final_status}."
        )
        self.db.add(audit)
        self.db.commit()

        return image_item
