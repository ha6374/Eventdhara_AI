import json
import logging
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.image import ImageItem
from app.models.category import Category
from app.models.metadata import ImageMetadata
from app.models.audit import AuditLog
from app.schemas.metadata import MetadataCreate, MetadataUpdate
from app.services.gemini_service import (
    gemini_service,
    GeminiMetadataError,
    GeminiQuotaError,
    GeminiAuthError,
    GeminiValidationError,
    ImageValidationError
)

logger = logging.getLogger("eventdhara.metadata_service")


class MetadataError(Exception):
    """Base exception for metadata operations."""
    pass


class MetadataNotFoundError(MetadataError):
    """Raised when the specified image is not found."""
    pass


class MetadataNotApprovedError(MetadataError):
    """Raised when trying to generate metadata for a non-approved image."""
    pass


class MetadataConcurrencyError(MetadataError):
    """Raised when an image is already in PROCESSING state."""
    pass


class MetadataGenerationError(MetadataError):
    """Raised when metadata generation fails."""
    pass


class MetadataService:
    def __init__(self, db: Session):
        self.db = db

    def generate_for_image(self, image_id: int, force_regenerate: bool = False) -> Tuple[ImageMetadata, str]:
        """
        Generates or regenerates structured catalog metadata for an approved image.
        Returns a tuple of (ImageMetadata, status_flag) where status_flag is 'SUCCESS' or 'ALREADY_COMPLETED'.

        Behavior rules:
        - If NOT force_regenerate:
            - If metadata_status == COMPLETED and ImageMetadata exists:
                Skip Gemini API call, return existing metadata, status_flag = 'ALREADY_COMPLETED'.
            - If metadata_status == PROCESSING:
                Raise MetadataConcurrencyError to prevent duplicate requests.
        - If force_regenerate:
            - If metadata_status == PROCESSING:
                Raise MetadataConcurrencyError to prevent overlapping generation.
            - Existing metadata is preserved untouched if Gemini fails.
            - Overwritten only after valid Gemini structured metadata is returned.
        - If image status != APPROVED:
            Raise MetadataNotApprovedError.
        - If Gemini fails:
            - If initial generation: metadata_status = FAILED, no record created.
            - If regenerate: metadata_status restored to COMPLETED, existing record intact.
            - Raise MetadataGenerationError with the real underlying error reason.
        """
        # Try database row locking if PostgreSQL is used
        try:
            if self.db.bind and self.db.bind.dialect.name == "postgresql":
                image = self.db.query(ImageItem).filter(ImageItem.id == image_id).with_for_update().first()
            else:
                image = self.db.query(ImageItem).filter(ImageItem.id == image_id).first()
        except Exception:
            image = self.db.query(ImageItem).filter(ImageItem.id == image_id).first()

        if not image:
            raise MetadataNotFoundError(f"Image #{image_id} not found.")

        # Rule: Generate metadata only after image approval
        if image.status != "APPROVED":
            logger.warning("Attempted metadata generation for non-approved image #%s (status: %s)", image_id, image.status)
            raise MetadataNotApprovedError(f"Image #{image_id} is not APPROVED (status: {image.status}). Metadata can only be generated for approved images.")

        existing_meta = self.db.query(ImageMetadata).filter(ImageMetadata.image_id == image_id).first()

        # Duplicate prevention check
        if not force_regenerate:
            if image.metadata_status == "COMPLETED" and existing_meta:
                logger.info("Image #%s metadata is already COMPLETED. Skipping Gemini API call.", image_id)
                return existing_meta, "ALREADY_COMPLETED"

        # Concurrency protection check
        if image.metadata_status == "PROCESSING":
            logger.warning("Image #%s metadata is currently PROCESSING. Preventing duplicate request.", image_id)
            raise MetadataConcurrencyError(f"Metadata generation is already in progress for image #{image_id}.")

        # Transition status to PROCESSING and commit to release row lock before external API call
        image.metadata_status = "PROCESSING"
        self.db.commit()

        # Resolve category information for metadata generation
        cat_name = image.category.name if image.category else "Celebration"
        parent_name = image.category.parent.name if image.category and image.category.parent else ""

        # Metadata generation uses Google Drive only.
        photo_link = image.drive_url or ""

        # Call Gemini Vision API
        try:
            if not image.drive_file_id:
                raise MetadataGenerationError('Google Drive file ID missing.')
            from app.services.drive_service import GoogleDriveService
            drive_image_bytes, drive_mime_type = GoogleDriveService(self.db).download_image_bytes(image.drive_file_id)
            if not drive_image_bytes:
                raise MetadataGenerationError('Google Drive image download failed.')
            meta_dict = gemini_service.generate_metadata(
                image_bytes=drive_image_bytes,
                image_mime_type=drive_mime_type,
                category_name=parent_name or cat_name,
                subcategory_name=cat_name if parent_name else "",
                photo_url=photo_link
            )
        except Exception as e:
            logger.error("Gemini metadata generation failed for image #%s: %s", image_id, e)
            self.db.rollback()
            img_reload = self.db.query(ImageItem).filter(ImageItem.id == image_id).first()
            if img_reload:
                if force_regenerate and existing_meta:
                    # Preserve existing metadata intact!
                    img_reload.metadata_status = "COMPLETED"
                else:
                    img_reload.metadata_status = "FAILED"
                self.db.commit()

            try:
                fail_audit = AuditLog(
                    action="REGENERATE_METADATA_FAILED" if force_regenerate else "GENERATE_METADATA_FAILED",
                    image_id=image_id,
                    details=f"Metadata generation failed: {str(e)}"[:1000]
                )
                self.db.add(fail_audit)
                self.db.commit()
            except Exception as audit_err:
                logger.warning("Failed to record failure in audit log: %s", audit_err)
                self.db.rollback()

            raise MetadataGenerationError(f"Generation failed: {str(e)}")

        # Gemini API returned valid structured metadata. Save or update record safely.
        try:
            target_meta = self.db.query(ImageMetadata).filter(ImageMetadata.image_id == image_id).first()
            if target_meta:
                # Update existing record (for regenerate)
                target_meta.name = meta_dict["name"]
                target_meta.short_description = meta_dict["short_description"]
                target_meta.long_description = meta_dict["long_description"]
                target_meta.inclusion = json.dumps(meta_dict["inclusion"])
                target_meta.faq = json.dumps(meta_dict["faq"])
                target_meta.note = meta_dict.get("note", "")
                target_meta.keywords = json.dumps(meta_dict["keywords"])
                target_meta.tags = json.dumps(meta_dict["tags"])
                if meta_dict.get("custom_fields"):
                    target_meta.custom_fields = json.dumps(meta_dict["custom_fields"])
            else:
                # Insert new record (enforces 1 record per image)
                target_meta = ImageMetadata(
                    image_id=image.id,
                    name=meta_dict["name"],
                    short_description=meta_dict["short_description"],
                    long_description=meta_dict["long_description"],
                    inclusion=json.dumps(meta_dict["inclusion"]),
                    faq=json.dumps(meta_dict["faq"]),
                    note=meta_dict.get("note", ""),
                    keywords=json.dumps(meta_dict["keywords"]),
                    tags=json.dumps(meta_dict["tags"]),
                    custom_fields=json.dumps(meta_dict["custom_fields"]) if meta_dict.get("custom_fields") else None
                )
                self.db.add(target_meta)

            img_record = self.db.query(ImageItem).filter(ImageItem.id == image_id).first()
            if img_record:
                img_record.metadata_status = "COMPLETED"

            self.db.commit()
            self.db.refresh(target_meta)

            audit_action = "REGENERATE_METADATA" if force_regenerate else "GENERATE_METADATA"
            audit = AuditLog(
                action=audit_action,
                image_id=image.id,
                details=f"Generated structured metadata: '{target_meta.name}'"
            )
            self.db.add(audit)
            self.db.commit()

            return target_meta, "SUCCESS"

        except IntegrityError as ie:
            self.db.rollback()
            logger.error("IntegrityError saving metadata for image #%s: %s", image_id, ie)
            existing_again = self.db.query(ImageMetadata).filter(ImageMetadata.image_id == image_id).first()
            if existing_again:
                img_record = self.db.query(ImageItem).filter(ImageItem.id == image_id).first()
                if img_record:
                    img_record.metadata_status = "COMPLETED"
                    self.db.commit()
                return existing_again, "ALREADY_COMPLETED"
            raise MetadataGenerationError(f"Database integrity error: {ie}")
        except Exception as db_err:
            self.db.rollback()
            logger.error("Database error saving metadata for image #%s: %s", image_id, db_err)
            img_reload = self.db.query(ImageItem).filter(ImageItem.id == image_id).first()
            if img_reload:
                if force_regenerate and existing_meta:
                    img_reload.metadata_status = "COMPLETED"
                else:
                    img_reload.metadata_status = "FAILED"
                self.db.commit()
            raise MetadataGenerationError(f"Database error saving metadata: {db_err}")

    def update_metadata(self, metadata_id: int, update_in: MetadataUpdate) -> Optional[ImageMetadata]:
        """
        Updates metadata fields, including inclusions, FAQs, tags, keywords, and custom fields.
        """
        meta_obj = self.db.query(ImageMetadata).filter(ImageMetadata.id == metadata_id).first()
        if not meta_obj:
            return None

        update_dict = update_in.model_dump(exclude_unset=True)
        for field, val in update_dict.items():
            if field in ["inclusion", "faq", "keywords", "tags"]:
                if isinstance(val, (list, dict)):
                    setattr(meta_obj, field, json.dumps(val))
                elif val is not None:
                    setattr(meta_obj, field, str(val))
            elif field == "custom_fields":
                if isinstance(val, dict):
                    setattr(meta_obj, field, json.dumps(val))
                elif val is not None:
                    setattr(meta_obj, field, str(val))
            else:
                setattr(meta_obj, field, val)

        self.db.commit()
        self.db.refresh(meta_obj)

        audit = AuditLog(
            action="UPDATE_METADATA",
            image_id=meta_obj.image_id,
            details=f"Metadata record #{meta_obj.id} manually edited by operator."
        )
        self.db.add(audit)
        self.db.commit()

        return meta_obj

    def _get_category_ids_including_descendants(self, category_id: int) -> List[int]:
        """Get selected category and all nested subcategory IDs."""
        category_ids = {category_id}
        pending = [category_id]

        while pending:
            current_id = pending.pop()
            children = (
                self.db.query(Category.id)
                .filter(Category.parent_id == current_id)
                .all()
            )

            for row in children:
                child_id = row[0]
                if child_id not in category_ids:
                    category_ids.add(child_id)
                    pending.append(child_id)

        return list(category_ids)

    def _delete_metadata_records(self, records: List[ImageMetadata], action: str, details: str) -> int:
        """Delete metadata rows only. Preserve original images and categories."""
        if not records:
            return 0

        deleted_count = len(records)

        try:
            for meta in records:
                image = self.db.query(ImageItem).filter(
                    ImageItem.id == meta.image_id
                ).first()

                if image:
                    image.metadata_status = "PENDING"

                self.db.add(AuditLog(
                    action=action,
                    image_id=meta.image_id,
                    details=f"{details} Metadata ID: {meta.id}"
                ))

                self.db.delete(meta)

            self.db.commit()
            return deleted_count

        except Exception:
            self.db.rollback()
            logger.exception("Metadata deletion failed")
            raise

    def delete_metadata(self, metadata_id: int) -> bool:
        """Delete one metadata record without deleting its image."""
        meta = self.db.query(ImageMetadata).filter(
            ImageMetadata.id == metadata_id
        ).first()

        if not meta:
            return False

        self._delete_metadata_records(
            [meta],
            "DELETE_METADATA",
            "Single metadata record deleted."
        )
        return True

    def delete_multiple_metadata(self, metadata_ids: List[int]) -> int:
        """Delete selected metadata records only."""
        unique_ids = list(dict.fromkeys(metadata_ids))

        if not unique_ids:
            return 0

        records = self.db.query(ImageMetadata).filter(
            ImageMetadata.id.in_(unique_ids)
        ).all()

        return self._delete_metadata_records(
            records,
            "BULK_DELETE_METADATA",
            "Selected metadata record deleted."
        )

    def delete_category_metadata(self, category_id: int) -> int:
        """Delete metadata belonging to a category and its descendants."""
        category_ids = self._get_category_ids_including_descendants(category_id)
        records = (
            self.db.query(ImageMetadata)
            .join(ImageItem, ImageMetadata.image_id == ImageItem.id)
            .filter(ImageItem.category_id.in_(category_ids))
            .all()
        )

        return self._delete_metadata_records(
            records,
            "CATEGORY_DELETE_METADATA",
            f"Metadata deleted for category ID {category_id}."
        )
