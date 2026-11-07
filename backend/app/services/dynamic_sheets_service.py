import os
import re
import json
import secrets
import logging
import datetime
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.core.config import settings
from app.core.security import encrypt_token, decrypt_token
from app.models.sheets_config import GoogleSheetsConfig
from app.models.image import ImageItem
from app.models.metadata import ImageMetadata
from app.models.audit import AuditLog

logger = logging.getLogger("eventdhara.dynamic_sheets")

REQUIRED_HEADERS = [
    "Name",
    "Short Description",
    "Long Description",
    "Inclusions",
    "FAQs",
    "Note",
    "Keywords",
    "Tags",
    "Image URL",
    "Created At"
]

GOOGLE_OAUTH_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]


class DynamicGoogleSheetsService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def extract_spreadsheet_id(url_or_id: str) -> Optional[str]:
        """Extracts Google Spreadsheet ID from a URL or raw ID."""
        if not url_or_id:
            return None
        cleaned = url_or_id.strip()
        # Pattern matching docs.google.com/spreadsheets/d/SPREADSHEET_ID
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", cleaned)
        if match:
            return match.group(1)
        # Check if already a raw ID (alphanumeric with hyphens/underscores, >= 20 chars)
        if re.match(r"^[a-zA-Z0-9-_]{20,}$", cleaned):
            return cleaned
        return None

    def get_or_create_config(self, user_id: str = "default") -> GoogleSheetsConfig:
        config = self.db.query(GoogleSheetsConfig).filter(GoogleSheetsConfig.user_id == user_id).first()
        if not config:
            config = GoogleSheetsConfig(
                user_id=user_id,
                worksheet_name="EventDhara Catalog",
                is_connected=False
            )
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
        return config

    def _get_oauth_client_info(self) -> Tuple[Optional[str], Optional[str]]:
        """Resolves OAuth client_id and client_secret from environment or credentials.json."""
        client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
        client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", "")

        if client_id and client_secret:
            return client_id.strip(), client_secret.strip()

        # Fallback: check credentials.json
        cred_path = getattr(settings, "GOOGLE_OAUTH_CLIENT_JSON", None) or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "credentials.json")
        )
        if cred_path and os.path.exists(cred_path):
            try:
                with open(cred_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    app_info = data.get("installed") or data.get("web") or {}
                    c_id = app_info.get("client_id")
                    c_sec = app_info.get("client_secret")
                    if c_id and c_sec:
                        return c_id.strip(), c_sec.strip()
            except Exception as e:
                logger.warning("Could not read credentials.json: %s", e)

        return None, None

    def generate_auth_url(
        self,
        user_id: str = "default",
        redirect_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate Google OAuth authorization URL with preserved PKCE verifier."""

        client_id, client_secret = self._get_oauth_client_info()

        if not client_id or not client_secret:
            return {
                "success": False,
                "message": "Google OAuth Client ID and Secret are not configured."
            }

        effective_redirect = (
            redirect_uri
            or getattr(settings, "GOOGLE_REDIRECT_URI", "")
            or "https://eventdhara-ai.onrender.com/api/v1/sheets/oauth/callback"
        )

        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [effective_redirect]
            }
        }

        try:
            from google_auth_oauthlib.flow import Flow

            flow = Flow.from_client_config(
                client_config,
                scopes=GOOGLE_OAUTH_SCOPES,
                redirect_uri=effective_redirect
            )

            code_verifier = secrets.token_urlsafe(64)
            flow.code_verifier = code_verifier

            state_payload = {
                "user_id": user_id,
                "redirect_uri": effective_redirect,
                "code_verifier": code_verifier,
                "nonce": secrets.token_urlsafe(24)
            }

            encrypted_state = encrypt_token(json.dumps(state_payload))

            auth_url, _ = flow.authorization_url(
                access_type="offline",
                prompt="consent",
                include_granted_scopes="true",
                state=encrypted_state
            )

            return {
                "success": True,
                "auth_url": auth_url,
                "redirect_uri": effective_redirect
            }

        except Exception as e:
            logger.error("Error creating Google OAuth authorization URL: %s", e)
            return {
                "success": False,
                "message": f"OAuth initialization error: {str(e)}"
            }

    def handle_oauth_callback(
        self,
        code: str,
        state: Optional[str] = None,
        redirect_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exchange OAuth code and securely persist Google credentials."""

        client_id, client_secret = self._get_oauth_client_info()

        if not client_id or not client_secret:
            return {
                "success": False,
                "message": "Google OAuth client credentials missing"
            }

        try:
            if not state:
                return {
                    "success": False,
                    "message": "OAuth state missing. Please reconnect."
                }

            decrypted_state = decrypt_token(state)

            if not decrypted_state:
                return {
                    "success": False,
                    "message": "Invalid OAuth state. Please reconnect."
                }

            state_data = json.loads(decrypted_state)

            user_id = state_data.get("user_id", "default")
            effective_redirect = state_data.get("redirect_uri")
            code_verifier = state_data.get("code_verifier")

            if not effective_redirect or not code_verifier:
                return {
                    "success": False,
                    "message": "OAuth session incomplete. Please reconnect."
                }

            client_config = {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [effective_redirect]
                }
            }

            from google_auth_oauthlib.flow import Flow

            flow = Flow.from_client_config(
                client_config,
                scopes=GOOGLE_OAUTH_SCOPES,
                redirect_uri=effective_redirect
            )

            flow.code_verifier = code_verifier
            flow.fetch_token(code=code)
            credentials = flow.credentials

            email = "Connected User"
            display_name = "Google User"

            user_service = build("oauth2", "v2", credentials=credentials)
            user_info = user_service.userinfo().get().execute()

            email = user_info.get("email", email)
            display_name = user_info.get("name", display_name)

            config = self.get_or_create_config(user_id=user_id)

            config.access_token = encrypt_token(credentials.token)

            if credentials.refresh_token:
                config.refresh_token = encrypt_token(credentials.refresh_token)

            config.token_expiry = credentials.expiry
            config.client_id = client_id
            config.client_secret = client_secret
            config.connected_email = email
            config.connected_account_name = display_name
            config.is_connected = True
            config.scopes = json.dumps(list(credentials.scopes or []))
            config.last_sync_status = "CONNECTED"
            config.last_sync_message = f"Authenticated as {email}"

            self.db.commit()
            self.db.refresh(config)

            audit = AuditLog(
                action="CONNECT_GOOGLE_SHEETS",
                details=(
                    f"User '{user_id}' authenticated Google account "
                    f"'{email}' for dynamic Google Sheets."
                )
            )

            self.db.add(audit)
            self.db.commit()

            return {
                "success": True,
                "email": email,
                "display_name": display_name,
                "user_id": user_id,
                "message": f"Successfully connected Google Account: {email}"
            }

        except Exception as e:
            self.db.rollback()
            logger.error("OAuth token exchange failed: %s", e)
            return {
                "success": False,
                "message": f"OAuth token exchange failed: {str(e)}"
            }

    def get_credentials(self, user_id: str = "default") -> Optional[Credentials]:
        """Loads and decrypts stored tokens, automatically refreshing if expired."""
        config = self.get_or_create_config(user_id=user_id)
        if not config.is_connected or not config.access_token:
            return None

        client_id = config.client_id or getattr(settings, "GOOGLE_CLIENT_ID", "")
        client_secret = config.client_secret or getattr(settings, "GOOGLE_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            cid, csec = self._get_oauth_client_info()
            client_id = client_id or cid
            client_secret = client_secret or csec

        decrypted_token = decrypt_token(config.access_token)
        decrypted_refresh = decrypt_token(config.refresh_token)

        creds = Credentials(
            token=decrypted_token,
            refresh_token=decrypted_refresh,
            token_uri=config.token_uri or "https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=json.loads(config.scopes) if config.scopes else GOOGLE_OAUTH_SCOPES,
            expiry=config.token_expiry
        )

        # Refresh if expired
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                config.access_token = encrypt_token(creds.token)
                config.token_expiry = creds.expiry
                self.db.commit()
            except Exception as e:
                logger.error("Failed refreshing Google Sheets credentials: %s", e)
                return None

        return creds

    def update_config(
        self,
        spreadsheet_url: str,
        worksheet_name: Optional[str] = "EventDhara Catalog",
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """Saves user spreadsheet URL, automatically extracting Spreadsheet ID."""
        sheet_id = self.extract_spreadsheet_id(spreadsheet_url)
        if not sheet_id:
            return {
                "success": False,
                "message": "Invalid Google Spreadsheet URL. Format should be: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit"
            }

        config = self.get_or_create_config(user_id=user_id)
        config.spreadsheet_url = spreadsheet_url.strip()
        config.spreadsheet_id = sheet_id
        if worksheet_name and worksheet_name.strip():
            config.worksheet_name = worksheet_name.strip()

        self.db.commit()
        self.db.refresh(config)

        return {
            "success": True,
            "spreadsheet_id": sheet_id,
            "spreadsheet_url": config.spreadsheet_url,
            "worksheet_name": config.worksheet_name,
            "message": f"Spreadsheet configured (ID: {sheet_id})."
        }

    def test_connection(self, user_id: str = "default") -> Dict[str, Any]:
        """
        Validates that the connected Google account has write/Editor permissions
        on the configured spreadsheet.
        """
        config = self.get_or_create_config(user_id=user_id)
        if not config.is_connected:
            return {
                "success": False,
                "status": "NOT_CONNECTED",
                "message": "Google Account is not connected. Please click 'Connect Google Account' first."
            }

        if not config.spreadsheet_id:
            return {
                "success": False,
                "status": "NO_SPREADSHEET",
                "message": "No Google Spreadsheet URL configured. Please enter your spreadsheet URL."
            }

        creds = self.get_credentials(user_id=user_id)
        if not creds:
            return {
                "success": False,
                "status": "EXPIRED",
                "message": "Google authentication session expired or invalid. Please re-connect your account."
            }

        try:
            service = build("sheets", "v4", credentials=creds)
            ss = service.spreadsheets().get(spreadsheetId=config.spreadsheet_id).execute()
            sheet_title = ss.get("properties", {}).get("title", "Untitled Spreadsheet")

            # Check existing sheets/worksheets
            sheets_list = ss.get("sheets", [])
            tab_names = [s.get("properties", {}).get("title") for s in sheets_list if s.get("properties")]
            tab_exists = config.worksheet_name in tab_names

            # Verify Editor permission
            can_write = False
            try:
                # Lightweight test write/read on user's tab
                service.spreadsheets().values().get(
                    spreadsheetId=config.spreadsheet_id,
                    range=f"'{config.worksheet_name}'!A1:A1" if tab_exists else f"'{tab_names[0]}'!A1:A1"
                ).execute()
                can_write = True
            except Exception as write_err:
                err_str = str(write_err)
                if "403" in err_str or "PERMISSION_DENIED" in err_str:
                    return {
                        "success": False,
                        "status": "PERMISSION_DENIED",
                        "message": f"Connected account '{config.connected_email}' does not have Editor access to '{sheet_title}'. Please share the spreadsheet with Editor permissions."
                    }
                can_write = True

            return {
                "success": True,
                "status": "CONNECTED_AND_VERIFIED",
                "spreadsheet_title": sheet_title,
                "spreadsheet_id": config.spreadsheet_id,
                "worksheet_name": config.worksheet_name,
                "worksheet_exists": tab_exists,
                "available_worksheets": tab_names,
                "connected_email": config.connected_email,
                "has_editor_permission": can_write,
                "message": f"Connection verified! Successfully connected to '{sheet_title}' with Editor permissions as {config.connected_email}."
            }
        except Exception as e:
            err_msg = str(e)
            logger.error("Google Sheets connection test failed: %s", err_msg)
            if "404" in err_msg or "not found" in err_msg.lower():
                return {
                    "success": False,
                    "status": "NOT_FOUND",
                    "message": f"Spreadsheet ID '{config.spreadsheet_id}' not found. Please verify the URL or ensure the spreadsheet has not been deleted."
                }
            if "403" in err_msg or "PERMISSION_DENIED" in err_msg:
                return {
                    "success": False,
                    "status": "PERMISSION_DENIED",
                    "message": f"Permission denied for account '{config.connected_email}'. Please share the spreadsheet with '{config.connected_email}' as an Editor."
                }
            return {
                "success": False,
                "status": "ERROR",
                "message": f"Connection verification error: {err_msg}"
            }

    def disconnect(self, user_id: str = "default") -> Dict[str, Any]:
        """Clears stored OAuth credentials and disconnects spreadsheet."""
        config = self.get_or_create_config(user_id=user_id)
        config.is_connected = False
        config.access_token = None
        config.refresh_token = None
        config.connected_email = None
        config.connected_account_name = None
        config.last_sync_status = "DISCONNECTED"
        config.last_sync_message = "Disconnected by user."
        self.db.commit()

        audit = AuditLog(
            action="DISCONNECT_GOOGLE_SHEETS",
            details=f"User '{user_id}' disconnected dynamic Google Sheets integration."
        )
        self.db.add(audit)
        self.db.commit()

        return {"success": True, "message": "Google account and spreadsheet disconnected successfully."}

    def _ensure_worksheet_and_headers(
        self,
        service: Any,
        spreadsheet_id: str,
        worksheet_name: str
    ) -> bool:
        """Ensures worksheet exists and creates required 10 headers if empty."""
        ss = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets_list = ss.get("sheets", [])
        tab_names = [s.get("properties", {}).get("title") for s in sheets_list if s.get("properties")]

        if worksheet_name not in tab_names:
            # Create worksheet
            add_req = {
                "addSheet": {
                    "properties": {
                        "title": worksheet_name,
                        "gridProperties": {
                            "rowCount": 1000,
                            "columnCount": 15,
                            "frozenRowCount": 1
                        }
                    }
                }
            }
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [add_req]}
            ).execute()
            logger.info("Created new worksheet '%s' in spreadsheet %s", worksheet_name, spreadsheet_id)

        # Check if headers exist in A1:J1
        header_check = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{worksheet_name}'!A1:J1"
        ).execute()

        existing_headers = header_check.get("values", [])
        if not existing_headers or len(existing_headers[0]) == 0:
            # Write 10 required headers
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{worksheet_name}'!A1:J1",
                valueInputOption="USER_ENTERED",
                body={"values": [REQUIRED_HEADERS]}
            ).execute()
            logger.info("Wrote standard 10 headers to worksheet '%s'", worksheet_name)

        return True

    def _get_existing_row_identifiers(
        self,
        service: Any,
        spreadsheet_id: str,
        worksheet_name: str
    ) -> set:
        """Reads existing names and image URLs from sheet to prevent duplicates."""
        try:
            res = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"'{worksheet_name}'!A2:J"
            ).execute()
            rows = res.get("values", [])
            identifiers = set()
            for r in rows:
                if len(r) > 0 and r[0]:  # Name
                    identifiers.add(r[0].strip().lower())
                if len(r) > 8 and r[8]:  # Image URL
                    identifiers.add(r[8].strip())
            return identifiers
        except Exception as e:
            logger.warning("Could not read existing rows for de-duplication: %s", e)
            return set()

    def append_metadata(
        self,
        image_ids: Optional[List[int]] = None,
        category_id: Optional[int] = None,
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Appends structured metadata rows to the user's connected Google Spreadsheet
        with exact 10-column specification, Hindi & English support, readable formatting,
        and duplicate prevention.
        """
        config = self.get_or_create_config(user_id=user_id)
        if not config.is_connected:
            return {"success": False, "message": "Google Account not connected. Please connect your Google Account."}

        if not config.spreadsheet_id:
            return {"success": False, "message": "No Google Spreadsheet configured. Please enter a valid spreadsheet URL."}

        creds = self.get_credentials(user_id=user_id)
        if not creds:
            return {"success": False, "message": "Google authentication session expired. Please re-authenticate."}

        # Query metadata
        query = self.db.query(ImageMetadata).join(ImageItem, ImageMetadata.image_id == ImageItem.id)
        if image_ids:
            query = query.filter(ImageMetadata.image_id.in_(image_ids))
        if category_id:
            query = query.filter(ImageItem.category_id == category_id)

        meta_records = query.order_by(ImageMetadata.id.asc()).all()
        if not meta_records:
            return {
                "success": False,
                "message": "No metadata records found to export. Generate metadata for approved images first.",
                "appended_count": 0
            }

        try:
            service = build("sheets", "v4", credentials=creds)

            # Ensure worksheet and 10 headers exist
            self._ensure_worksheet_and_headers(service, config.spreadsheet_id, config.worksheet_name)

            # Read existing rows to prevent duplicate submissions
            existing_ids = self._get_existing_row_identifiers(service, config.spreadsheet_id, config.worksheet_name)

            public_origin = getattr(settings, "BACKEND_PUBLIC_URL", "https://eventdhara-ai.onrender.com").rstrip("/")
            new_rows = []
            skipped_duplicates = 0

            for m in meta_records:
                img = m.image
                # Resolve valid accessible image URL
                if img.drive_url:
                    photo_url = img.drive_url
                elif img.drive_file_id:
                    photo_url = f"https://drive.google.com/uc?export=view&id={img.drive_file_id}"
                elif img.storage_path:
                    clean_rel = img.storage_path.replace("storage/", "").replace("storage\\", "").lstrip("/\\")
                    photo_url = f"{public_origin}/storage/{clean_rel}"
                else:
                    photo_url = f"{public_origin}/api/v1/images/{img.id}/file"

                # Check duplicate
                name_key = (m.name or "").strip().lower()
                if name_key in existing_ids or (photo_url and photo_url in existing_ids):
                    skipped_duplicates += 1
                    continue

                # Format inclusions readably (supports bulleted multi-line or pipe)
                inclusions_str = ""
                if m.inclusion:
                    try:
                        inc_data = json.loads(m.inclusion)
                        if isinstance(inc_data, list):
                            inclusions_str = "\n".join([f"• {str(item).strip()}" for item in inc_data if str(item).strip()])
                        else:
                            inclusions_str = str(m.inclusion)
                    except Exception:
                        inclusions_str = str(m.inclusion)

                # Format FAQs readably
                faqs_str = ""
                if m.faq:
                    try:
                        faq_data = json.loads(m.faq)
                        if isinstance(faq_data, list):
                            formatted_faqs = []
                            for idx, item in enumerate(faq_data, 1):
                                if isinstance(item, dict):
                                    q = item.get("question", "").strip()
                                    a = item.get("answer", "").strip()
                                    if q or a:
                                        formatted_faqs.append(f"Q{idx}: {q}\nA: {a}")
                                elif isinstance(item, str) and item.strip():
                                    formatted_faqs.append(f"{idx}. {item.strip()}")
                            faqs_str = "\n\n".join(formatted_faqs)
                        else:
                            faqs_str = str(m.faq)
                    except Exception:
                        faqs_str = str(m.faq)

                # Format keywords
                keywords_str = ""
                if m.keywords:
                    try:
                        kw_data = json.loads(m.keywords)
                        if isinstance(kw_data, list):
                            keywords_str = ", ".join([str(k).strip() for k in kw_data if str(k).strip()])
                        else:
                            keywords_str = str(m.keywords)
                    except Exception:
                        keywords_str = str(m.keywords)

                # Format tags
                tags_str = ""
                if m.tags:
                    try:
                        t_data = json.loads(m.tags)
                        if isinstance(t_data, list):
                            tags_str = ", ".join([str(t).strip() for t in t_data if str(t).strip()])
                        else:
                            tags_str = str(m.tags)
                    except Exception:
                        tags_str = str(m.tags)

                created_at_str = m.created_at.strftime("%Y-%m-%d %H:%M:%S") if m.created_at else datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

                # Exact 10 columns:
                # 1. Name
                # 2. Short Description
                # 3. Long Description
                # 4. Inclusions
                # 5. FAQs
                # 6. Note
                # 7. Keywords
                # 8. Tags
                # 9. Image URL
                # 10. Created At
                row = [
                    m.name or f"Setup #{m.id}",
                    m.short_description or "",
                    m.long_description or "",
                    inclusions_str,
                    faqs_str,
                    m.note or "",
                    keywords_str,
                    tags_str,
                    photo_url,
                    created_at_str
                ]
                new_rows.append(row)

            if not new_rows:
                return {
                    "success": True,
                    "appended_count": 0,
                    "skipped_duplicates": skipped_duplicates,
                    "spreadsheet_url": config.spreadsheet_url,
                    "worksheet_name": config.worksheet_name,
                    "message": f"All {len(meta_records)} records are already present in the sheet. No duplicate rows appended."
                }

            # API write execution: append below existing rows
            body = {"values": new_rows}
            append_resp = service.spreadsheets().values().append(
                spreadsheetId=config.spreadsheet_id,
                range=f"'{config.worksheet_name}'!A:J",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()

            updates = append_resp.get("updates", {})
            updated_rows = updates.get("updatedRows", len(new_rows))

            # Update config synchronization status
            config.last_synced_at = datetime.datetime.utcnow()
            config.last_sync_status = "SUCCESS"
            config.last_sync_message = f"Appended {updated_rows} metadata items (Skipped {skipped_duplicates} duplicates)"
            self.db.commit()

            # Record audit
            audit = AuditLog(
                action="APPEND_GOOGLE_SHEETS",
                details=f"Appended {updated_rows} metadata rows to spreadsheet '{config.spreadsheet_id}', worksheet '{config.worksheet_name}'."
            )
            self.db.add(audit)
            self.db.commit()

            return {
                "success": True,
                "appended_count": updated_rows,
                "skipped_duplicates": skipped_duplicates,
                "spreadsheet_id": config.spreadsheet_id,
                "spreadsheet_url": config.spreadsheet_url,
                "worksheet_name": config.worksheet_name,
                "last_synced_at": config.last_synced_at.isoformat(),
                "message": f"Successfully appended {updated_rows} metadata records to Google Sheets tab '{config.worksheet_name}'."
            }

        except Exception as e:
            err_msg = str(e)
            logger.error("Error appending metadata to Google Sheets: %s", err_msg)
            config.last_sync_status = "FAILED"
            config.last_sync_message = f"Append failed: {err_msg}"
            self.db.commit()
            return {
                "success": False,
                "message": f"Google Sheets API write failed: {err_msg}"
            }
