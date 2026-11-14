import os
import json
import pandas as pd
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.image import ImageItem
from app.models.category import Category
from app.models.metadata import ImageMetadata
from app.core.config import settings


class ExportService:
    def __init__(self, db: Session):
        self.db = db


    def _get_category_ids_including_descendants(self, category_id: int):
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

    def export_images_data(
        self,
        status: Optional[str] = None,
        category_id: Optional[int] = None,
        export_format: str = "csv"  # csv or excel
    ) -> str:
        query = self.db.query(ImageItem)
        if status:
            query = query.filter(ImageItem.status == status.upper())
        if category_id is not None:
            category_ids = self._get_category_ids_including_descendants(category_id)
            query = query.filter(ImageItem.category_id.in_(category_ids))

        images = query.all()

        records = []
        for img in images:
            cat_name = img.category.name if img.category else "Unassigned"
            parent_name = img.category.parent.name if img.category and img.category.parent else ""

            meta_name = ""
            meta_desc = ""
            tags_str = ""
            if img.metadata_rel:
                meta_name = img.metadata_rel.name
                meta_desc = img.metadata_rel.short_description
                try:
                    tags_str = ", ".join(json.loads(img.metadata_rel.tags or "[]"))
                except Exception:
                    tags_str = img.metadata_rel.tags or ""

            records.append({
                "Image ID": img.id,
                "Filename": img.original_filename,
                "Status": img.status,
                "Category": parent_name or cat_name,
                "Subcategory": cat_name if parent_name else "",
                "Quality Status": img.quality_status,
                "Blur Score": round(img.blur_score, 2) if img.blur_score else None,
                "Dimensions": f"{img.width}x{img.height}",
                "File Size (KB)": round(img.file_size / 1024, 1),
                "AI Confidence": f"{round(img.ai_confidence * 100, 1)}%" if img.ai_confidence else None,
                "Rejection Reason": img.rejection_reason or "",
                "Review Reason": img.review_reason or "",
                "Is Duplicate": "Yes" if img.is_duplicate else "No",
                "Product Title": meta_name,
                "Short Description": meta_desc,
                "Tags": tags_str,
                "Google Drive URL": img.drive_url or "",
                "Created At": img.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })

        df = pd.DataFrame(records)
        export_dir = os.path.join(settings.STORAGE_ROOT, "exports")
        os.makedirs(export_dir, exist_ok=True)

        status_tag = status.lower() if status else "all"
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")

        if export_format.lower() == "excel" or export_format.lower() == "xlsx":
            file_name = f"eventdhara_{status_tag}_export_{timestamp}.xlsx"
            file_path = os.path.join(export_dir, file_name)
            df.to_excel(file_path, index=False, engine="openpyxl")
        else:
            file_name = f"eventdhara_{status_tag}_export_{timestamp}.csv"
            file_path = os.path.join(export_dir, file_name)
            df.to_csv(file_path, index=False)

        return file_path
