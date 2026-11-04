import os
import json
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.models.image import ImageItem
from app.models.metadata import ImageMetadata
from app.models.audit import AuditLog
from app.core.config import settings
from app.schemas.metadata import MetadataCreate, MetadataUpdate
from app.services.gemini_service import gemini_service

logger = logging.getLogger("eventdhara.metadata_service")


class MetadataService:
    def __init__(self, db: Session):
        self.db = db

    def generate_for_image(self, image_id: int, force_regenerate: bool = False) -> Optional[ImageMetadata]:
        """
        Generates or regenerates structured 9-field catalog metadata for an approved image.
        """
        image = self.db.query(ImageItem).filter(ImageItem.id == image_id).first()
        if not image:
            return None

        # Rule: Generate metadata only after image approval
        if image.status != "APPROVED":
            logger.warning("Attempted to generate metadata for non-approved image ID %s (status: %s)", image_id, image.status)
            return None

        image.metadata_status = "PROCESSING"
        self.db.commit()

        try:
            cat_name = image.category.name if image.category else "Celebration"
            parent_name = image.category.parent.name if image.category and image.category.parent else ""

            # Resolve source file path safely
            source_file = image.file_path
            if not os.path.isabs(source_file):
                source_file = os.path.abspath(os.path.join(settings.STORAGE_ROOT, "processed", image.filename))

            if not os.path.exists(source_file):
                alt = os.path.abspath(os.path.join(settings.STORAGE_ROOT, "processed", image.filename))
                if os.path.exists(alt):
                    source_file = alt

            photo_link = image.drive_url or f"/{image.storage_path}"

            meta_dict = gemini_service.generate_metadata(
                image_path=source_file,
                category_name=parent_name or cat_name,
                subcategory_name=cat_name if parent_name else "",
                photo_url=photo_link
            )

            # Check existing metadata
            existing = self.db.query(ImageMetadata).filter(ImageMetadata.image_id == image_id).first()
            if existing:
                existing.name = meta_dict.get("name", f"{cat_name} Decor Setup #{image.id}")
                existing.short_description = meta_dict.get("short_description", "")
                existing.long_description = meta_dict.get("long_description", "")
                existing.inclusion = json.dumps(meta_dict.get("inclusion", []))
                existing.faq = json.dumps(meta_dict.get("faq", []))
                existing.note = meta_dict.get("note", "")
                existing.keywords = json.dumps(meta_dict.get("keywords", []))
                existing.tags = json.dumps(meta_dict.get("tags", []))
                meta_obj = existing
            else:
                meta_obj = ImageMetadata(
                    image_id=image.id,
                    name=meta_dict.get("name", f"{cat_name} Decor Setup #{image.id}"),
                    short_description=meta_dict.get("short_description", ""),
                    long_description=meta_dict.get("long_description", ""),
                    inclusion=json.dumps(meta_dict.get("inclusion", [])),
                    faq=json.dumps(meta_dict.get("faq", [])),
                    note=meta_dict.get("note", ""),
                    keywords=json.dumps(meta_dict.get("keywords", [])),
                    tags=json.dumps(meta_dict.get("tags", []))
                )
                self.db.add(meta_obj)

            image.metadata_status = "COMPLETED"
            self.db.commit()
            self.db.refresh(meta_obj)

            audit_action = "REGENERATE_METADATA" if force_regenerate else "GENERATE_METADATA"
            audit = AuditLog(
                action=audit_action,
                image_id=image.id,
                details=f"Generated structured metadata: '{meta_obj.name}'"
            )
            self.db.add(audit)
            self.db.commit()

            return meta_obj

        except Exception as e:
            logger.error("Failed to generate metadata for image ID %s: %s", image_id, e)
            image.metadata_status = "FAILED"
            self.db.commit()
            return None

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
