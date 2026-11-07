import os
import shutil
import datetime
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.models.image import ImageItem
from app.models.category import Category
from app.models.audit import AuditLog
from app.core.config import settings

logger = logging.getLogger("eventdhara.drive_service")


class GoogleDriveService:
    def __init__(self, db: Session):
        self.db = db
        self.token_file = getattr(settings, "GOOGLE_DRIVE_TOKEN_JSON", None) or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "token.json")
        )
        self.client_file = getattr(settings, "GOOGLE_OAUTH_CLIENT_JSON", None) or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "credentials.json")
        )
        self.root_folder_id = getattr(settings, "GOOGLE_DRIVE_ROOT_FOLDER_ID", "19BGF1jSqlilxTnEDuaZldYb2yp25yedJ")
        self.root_folder_name = getattr(settings, "GOOGLE_DRIVE_ROOT_FOLDER_NAME", "Eventdhara_decorations")

    def _get_drive_client(self):
        """Builds Drive API client using encrypted OAuth credentials stored in PostgreSQL."""
        try:
            from googleapiclient.discovery import build
            from app.services.dynamic_sheets_service import DynamicGoogleSheetsService

            creds = DynamicGoogleSheetsService(self.db).get_credentials(
                user_id="default"
            )

            if not creds or not creds.valid:
                return None

            required_scope = "https://www.googleapis.com/auth/drive"
            granted_scopes = set(creds.scopes or [])

            if required_scope not in granted_scopes:
                logger.warning(
                    "Google OAuth token lacks full Drive permission. Reconnect Google account."
                )
                return None

            return build("drive", "v3", credentials=creds)

        except Exception as e:
            logger.error("Error creating Google Drive API client: %s", e)
            return None

    def get_connection_status(self) -> Dict[str, Any]:
        """
        Queries Google Drive API for account identity, storage quotas, and folder details.
        """
        drive = self._get_drive_client()
        if not drive:
            return {
                "connected": False,
                "status": "DISCONNECTED",
                "message": "Google Drive OAuth is not connected or the stored token lacks Drive permission.",
                "root_folder_id": self.root_folder_id,
                "root_folder_name": self.root_folder_name
            }

        try:
            about = drive.about().get(fields="user, storageQuota").execute()
            user = about.get("user", {})
            quota = about.get("storageQuota", {})

            # Verify root folder
            root_info = drive.files().get(fileId=self.root_folder_id, fields="id, name").execute()

            limit_bytes = int(quota.get("limit", 0))
            usage_bytes = int(quota.get("usage", 0))

            return {
                "connected": True,
                "status": "AUTHENTICATED",
                "email": user.get("emailAddress", "Connected User"),
                "display_name": user.get("displayName", "Google Drive Account"),
                "photo_url": user.get("photoLink", ""),
                "root_folder_id": root_info.get("id", self.root_folder_id),
                "root_folder_name": root_info.get("name", self.root_folder_name),
                "storage_used_bytes": usage_bytes,
                "storage_limit_bytes": limit_bytes,
                "storage_used_gb": round(usage_bytes / (1024 ** 3), 2),
                "storage_limit_gb": round(limit_bytes / (1024 ** 3), 2) if limit_bytes > 0 else "Unlimited"
            }
        except Exception as e:
            logger.error("Error checking Drive connection status: %s", e)
            return {
                "connected": False,
                "status": "ERROR",
                "message": f"Connection check failed: {str(e)}",
                "root_folder_id": self.root_folder_id,
                "root_folder_name": self.root_folder_name
            }

    def list_folders(self, parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists folders inside target Google Drive folder."""
        drive = self._get_drive_client()
        if not drive:
            return []

        target_parent = parent_id or self.root_folder_id
        try:
            q = f"mimeType='application/vnd.google-apps.folder' and trashed=false and '{target_parent}' in parents"
            res = drive.files().list(q=q, fields="files(id, name, modifiedTime)").execute()
            return res.get("files", [])
        except Exception as e:
            logger.error("Error listing Drive folders: %s", e)
            return []

    def create_drive_folder(self, name: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """Creates a new folder on Google Drive."""
        drive = self._get_drive_client()
        if not drive:
            return {"success": False, "message": "Google Drive client not connected"}

        target_parent = parent_id or self.root_folder_id
        try:
            folder = drive.files().create(
                body={
                    "name": name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [target_parent]
                },
                fields="id, name, webViewLink"
            ).execute()
            return {
                "success": True,
                "folder_id": folder["id"],
                "folder_name": folder["name"],
                "folder_url": folder.get("webViewLink", "")
            }
        except Exception as e:
            logger.error("Error creating Drive folder '%s': %s", name, e)
            return {"success": False, "message": str(e)}

    def get_or_create_path_folders(self, folder_names: List[str]) -> str:
        """
        Navigates or creates nested folder path on Google Drive:
        e.g. ["Wedding", "Approved"] inside the root folder.
        Returns the final folder ID.
        """
        drive = self._get_drive_client()
        if not drive:
            return self.root_folder_id

        current_parent = self.root_folder_id
        for name in folder_names:
            clean_name = name.replace("/", "-").replace("\\", "-").strip()
            # Check if folder exists
            q = f"mimeType='application/vnd.google-apps.folder' and trashed=false and '{current_parent}' in parents and name='{clean_name}'"
            res = drive.files().list(q=q, fields="files(id, name)").execute()
            files = res.get("files", [])
            if files:
                current_parent = files[0]["id"]
            else:
                new_folder = drive.files().create(
                    body={
                        "name": clean_name,
                        "mimeType": "application/vnd.google-apps.folder",
                        "parents": [current_parent]
                    },
                    fields="id"
                ).execute()
                current_parent = new_folder["id"]

        return current_parent

    def upload_approved_image(self, image_id: int) -> Dict[str, Any]:
        """
        Uploads an approved image to Google Drive category hierarchy:
        Eventdhara_decorations / {Category} / Approved / {Original_Filename}
        """
        return self.upload_image_to_drive(image_id, force_status="APPROVED")

    def upload_image_to_drive(self, image_id: int, force_status: Optional[str] = None) -> Dict[str, Any]:
        """
        Uploads any image (Approved, Rejected, or Review) to Google Drive in its proper category folder.
        """
        image = self.db.query(ImageItem).filter(ImageItem.id == image_id).first()
        if not image:
            return {"success": False, "message": "Image not found"}

        image_status = str(
            getattr(image.status, "value", image.status)
        ).upper()

        if image_status != "APPROVED":
            return {
                "success": False,
                "message": "Only approved images can be uploaded to Google Drive."
            }

        if image.drive_status == "COMPLETED" and image.drive_file_id:
            return {
                "success": True,
                "drive_file_id": image.drive_file_id,
                "drive_url": image.drive_url,
                "message": "Image is already uploaded to Google Drive."
            }

        image.drive_status = "UPLOADING"
        self.db.commit()

        # Resolve category folder name and status
        from app.services.category_storage import get_canonical_category_name, get_status_folder_name
        cat_folder = get_canonical_category_name(image.category)
        status_name = force_status or image.status
        status_folder = get_status_folder_name(status_name)

        # Source file on disk
        source_file = image.file_path
        if not os.path.exists(source_file):
            alt = os.path.abspath(os.path.join(settings.STORAGE_ROOT, "processed", image.filename))
            if os.path.exists(alt):
                source_file = alt
            else:
                image.drive_status = "FAILED"
                self.db.commit()
                return {"success": False, "message": f"Source image file not found on disk: {source_file}"}

        # Local mirror sync
        mirror_dir = os.path.join(settings.STORAGE_ROOT, "approved", self.root_folder_name, cat_folder, status_folder)
        os.makedirs(mirror_dir, exist_ok=True)
        mirror_path = os.path.join(mirror_dir, image.original_filename)
        shutil.copy2(source_file, mirror_path)

        drive = self._get_drive_client()
        if not drive:
            image.drive_status = "FAILED"
            self.db.commit()
            return {
                "success": False,
                "message": "Google Drive is not connected. No file was uploaded."
            }

        try:
            from googleapiclient.http import MediaFileUpload

            # Get target parent folder in Drive
            target_folder_id = self.get_or_create_path_folders([cat_folder, status_folder])

            mime = "image/jpeg" if image.format.upper() in ["JPEG", "JPG"] else f"image/{image.format.lower()}"
            media = MediaFileUpload(source_file, mimetype=mime, resumable=True)

            drive_file = drive.files().create(
                body={
                    "name": image.original_filename,
                    "parents": [target_folder_id]
                },
                media_body=media,
                fields="id, name, webViewLink"
            ).execute()

            drive_id = drive_file.get("id")

            if not drive_id:
                raise RuntimeError("Google Drive did not return a valid file ID.")

            drive_url = drive_file.get("webViewLink") or f"https://drive.google.com/file/d/{drive_id}/view"

            image.drive_status = "COMPLETED"
            image.drive_file_id = drive_id
            image.drive_url = drive_url
            image.drive_uploaded_at = datetime.datetime.utcnow()
            self.db.commit()

            audit = AuditLog(
                action="DRIVE_UPLOAD",
                image_id=image.id,
                details=f"Uploaded to Google Drive ({cat_folder}/{status_folder}): '{image.original_filename}' ({drive_id})"
            )
            self.db.add(audit)
            self.db.commit()

            return {
                "success": True,
                "drive_file_id": drive_id,
                "drive_url": drive_url,
                "folder_path": f"{self.root_folder_name} / {cat_folder} / {status_folder}",
                "message": "Successfully uploaded to Google Drive"
            }

        except Exception as e:
            logger.error("Drive upload exception for image %s: %s", image_id, e)
            image.drive_status = "FAILED"
            self.db.commit()
            return {"success": False, "message": f"Google Drive API error: {str(e)}"}

    def get_drive_folder_hierarchy(self) -> List[Dict[str, Any]]:
        """
        Returns full category tree annotated with Google Drive sync counts.
        """
        root_categories = self.db.query(Category).filter(Category.parent_id == None).order_by(Category.name.asc()).all()

        def build_node(cat: Category, parent_path: str) -> Dict[str, Any]:
            current_path = f"{parent_path}/{cat.name}" if parent_path else cat.name

            descendant_ids = [cat.id]
            def collect_ids(parent_c: Category):
                for ch in parent_c.children:
                    descendant_ids.append(ch.id)
                    collect_ids(ch)
            collect_ids(cat)

            approved_query = self.db.query(ImageItem).filter(
                ImageItem.category_id.in_(descendant_ids),
                ImageItem.status == "APPROVED"
            )
            total_approved = approved_query.count()
            synced_count = approved_query.filter(ImageItem.drive_status == "COMPLETED").count()
            pending_count = total_approved - synced_count

            children_nodes = [build_node(child, current_path) for child in cat.children]

            return {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
                "cloud_path": f"{self.root_folder_name}/{current_path}",
                "total_approved": total_approved,
                "synced_count": synced_count,
                "pending_count": pending_count,
                "children": children_nodes
            }

        return [build_node(root, "") for root in root_categories]

    def upload_category_folder(self, category_id: int) -> Dict[str, Any]:
        """Uploads all approved images in a category to Google Drive."""
        cat = self.db.query(Category).filter(Category.id == category_id).first()
        if not cat:
            return {"success": False, "message": "Category not found"}

        cat_ids = [cat.id]
        def collect_descendants(c: Category):
            for ch in c.children:
                cat_ids.append(ch.id)
                collect_descendants(ch)
        collect_descendants(cat)

        approved_images = (
            self.db.query(ImageItem)
            .filter(
                ImageItem.category_id.in_(cat_ids),
                ImageItem.status == "APPROVED",
                ImageItem.drive_status != "COMPLETED"
            )
            .all()
        )

        synced = 0
        failed = 0
        for img in approved_images:
            res = self.upload_approved_image(img.id)
            if res.get("success"):
                synced += 1
            else:
                failed += 1

        return {
            "success": True,
            "category_name": cat.name,
            "total_attempted": len(approved_images),
            "synced": synced,
            "failed": failed
        }

    def disconnect_drive(self) -> Dict[str, Any]:
        """Safely disconnects Google Drive by renaming or removing token file."""
        if os.path.exists(self.token_file):
            backup_token = f"{self.token_file}.bak"
            try:
                shutil.move(self.token_file, backup_token)
                return {"success": True, "message": "Google Drive successfully disconnected."}
            except Exception as e:
                return {"success": False, "message": f"Failed disconnecting Drive: {str(e)}"}
        return {"success": True, "message": "Google Drive is already disconnected."}
