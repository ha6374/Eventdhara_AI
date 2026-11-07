import os
import json
import logging
from typing import Optional, Dict, Any, List
from io import BytesIO
import pandas as pd
from sqlalchemy.orm import Session
from app.models.image import ImageItem
from app.models.category import Category
from app.models.metadata import ImageMetadata
from app.models.audit import AuditLog
from app.core.config import settings

logger = logging.getLogger("eventdhara.sheets_service")


class GoogleSheetsService:
    def __init__(self, db: Session):
        self.db = db

    def _get_drive_client(self):
        """Build Drive API client using encrypted OAuth credentials from PostgreSQL."""
        try:
            from googleapiclient.discovery import build
            from app.services.dynamic_sheets_service import DynamicGoogleSheetsService

            creds = DynamicGoogleSheetsService(self.db).get_credentials(
                user_id="default"
            )

            if not creds or not creds.valid:
                logger.error("Google Drive credentials are unavailable or invalid.")
                return None

            required_scope = "https://www.googleapis.com/auth/drive"
            granted_scopes = set(creds.scopes or [])

            if required_scope not in granted_scopes:
                logger.error("Google OAuth token does not have full Drive permission.")
                return None

            return build("drive", "v3", credentials=creds)

        except Exception:
            logger.exception("Failed to initialize Google Drive client for Sheets.")
            return None

    def export_metadata_to_sheets(
        self,
        category_id: Optional[int] = None,
        status: Optional[str] = "APPROVED",
        title_prefix: str = "EventDhara Product Catalog"
    ) -> Dict[str, Any]:
        """
        Exports all structured metadata rows into a native Google Sheet on Google Drive
        with exact 16-column specification and category-wise tabs or sections.
        """
        query = self.db.query(ImageItem)
        if status:
            query = query.filter(ImageItem.status == status.upper())
        if category_id:
            query = query.filter(ImageItem.category_id == category_id)

        images = query.order_by(ImageItem.id.asc()).all()
        if not images:
            return {
                "success": False,
                "message": "No images found matching export criteria",
                "total_rows": 0
            }

        rows = []
        for img in images:
            meta = img.metadata_rel
            cat_name = img.category.name if img.category else "Other"
            parent_name = img.category.parent.name if img.category and img.category.parent else ""
            full_cat = f"{parent_name} / {cat_name}" if parent_name else cat_name

            name = meta.name if meta else f"Setup #{img.id}"
            short_desc = meta.short_description if meta else ""
            long_desc = meta.long_description if meta else ""

            # Format inclusion
            inclusion_str = ""
            if meta and meta.inclusion:
                try:
                    inc_list = json.loads(meta.inclusion)
                    inclusion_str = " | ".join(inc_list) if isinstance(inc_list, list) else str(meta.inclusion)
                except Exception:
                    inclusion_str = str(meta.inclusion)

            # Format FAQ
            faq_str = ""
            if meta and meta.faq:
                try:
                    faq_items = json.loads(meta.faq)
                    if isinstance(faq_items, list):
                        faq_str = " ; ".join([f"Q: {q.get('question')} A: {q.get('answer')}" for q in faq_items if isinstance(q, dict)])
                    else:
                        faq_str = str(meta.faq)
                except Exception:
                    faq_str = str(meta.faq)

            note_str = meta.note if meta else ""

            # Format keywords & tags
            kw_str = ""
            if meta and meta.keywords:
                try:
                    kw_list = json.loads(meta.keywords)
                    kw_str = ", ".join(kw_list) if isinstance(kw_list, list) else str(meta.keywords)
                except Exception:
                    kw_str = str(meta.keywords)

            tags_str = ""
            if meta and meta.tags:
                try:
                    tags_list = json.loads(meta.tags)
                    tags_str = ", ".join(tags_list) if isinstance(tags_list, list) else str(meta.tags)
                except Exception:
                    tags_str = str(meta.tags)

            # Export only verified permanent Google Drive URLs.
            photo_url = None
            drive_id = str(img.drive_file_id or "").strip()

            if (
                getattr(img, "drive_status", None) == "COMPLETED"
                and drive_id
                and not drive_id.startswith(("gdrive_file_", "gdrive_"))
            ):
                photo_url = f"https://drive.google.com/file/d/{drive_id}/view"

            rows.append({
                "Image ID": img.id,
                "Category": full_cat,
                "Name": name,
                "Photo": photo_url,
                "Short Description": short_desc,
                "Long Description": long_desc,
                "Inclusion": inclusion_str,
                "FAQ": faq_str,
                "Note": note_str,
                "Keywords": kw_str,
                "Tags": tags_str,
                "Approval Status": img.status,
                "Original Filename": img.original_filename,
                "Image URL": photo_url,
                "Created Date": img.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Updated Date": img.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            })

        df = pd.DataFrame(rows)

        # 1. Generate in-memory Excel spreadsheet with category grouping
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            # Master Sheet
            df.to_excel(writer, sheet_name="All Metadata", index=False)
            # Category-wise split sheets
            for cat, group in df.groupby("Category"):
                clean_sheet_name = str(cat)[:30].replace("/", "-").replace("\\", "-").replace(":", "-")
                group.to_excel(writer, sheet_name=clean_sheet_name, index=False)

        excel_bytes = excel_buffer.getvalue()

        # 2. Upload to Google Drive and convert to native Google Sheet
        drive = self._get_drive_client()
        if not drive:
            # Save local backup in storage/exports
            export_path = os.path.join(settings.STORAGE_ROOT, "exports", "EventDhara_GoogleSheets_Export.xlsx")
            with open(export_path, "wb") as f:
                f.write(excel_bytes)
            return {
                "success": False,
                "status": "LOCAL_SAVED",
                "message": "Google Drive is unavailable. Excel backup saved locally; Google Sheets export was not completed.",
                "local_file": export_path,
                "total_rows": len(rows)
            }

        try:
            from googleapiclient.http import MediaInMemoryUpload

            media = MediaInMemoryUpload(
                excel_bytes,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                resumable=True
            )

            parent_folder_id = getattr(settings, "GOOGLE_DRIVE_ROOT_FOLDER_ID", "19BGF1jSqlilxTnEDuaZldYb2yp25yedJ")
            sheet_title = f"{title_prefix} - {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}"

            drive_file = drive.files().create(
                body={
                    "name": sheet_title,
                    "mimeType": "application/vnd.google-apps.spreadsheet",
                    "parents": [parent_folder_id]
                },
                media_body=media,
                fields="id, name, webViewLink"
            ).execute()

            sheet_id = drive_file.get("id")
            sheet_url = drive_file.get("webViewLink") or f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"

            # Audit log
            audit = AuditLog(
                action="EXPORT_GOOGLE_SHEETS",
                details=f"Exported {len(rows)} catalog items to Google Sheets: '{sheet_title}' ({sheet_id})"
            )
            self.db.add(audit)
            self.db.commit()

            return {
                "success": True,
                "status": "PUBLISHED",
                "sheet_id": sheet_id,
                "sheet_title": sheet_title,
                "sheet_url": sheet_url,
                "total_rows": len(rows),
                "message": f"Successfully published {len(rows)} catalog items to Google Sheets."
            }

        except Exception as e:
            logger.error("Failed uploading Google Sheet to Drive: %s", e)
            return {
                "success": False,
                "status": "ERROR",
                "message": f"Google Sheets write error: {str(e)}",
                "total_rows": len(rows)
            }
