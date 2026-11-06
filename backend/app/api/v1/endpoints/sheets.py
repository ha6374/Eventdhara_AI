import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.dynamic_sheets_service import DynamicGoogleSheetsService

logger = logging.getLogger("eventdhara.sheets_endpoints")
router = APIRouter()


class SheetsConfigUpdateRequest(BaseModel):
    spreadsheet_url: str
    worksheet_name: Optional[str] = "EventDhara Catalog"


class SheetsSyncRequest(BaseModel):
    image_ids: Optional[List[int]] = None
    category_id: Optional[int] = None


class SheetsConfigResponse(BaseModel):
    is_connected: bool
    connected_email: Optional[str] = None
    connected_account_name: Optional[str] = None
    spreadsheet_url: Optional[str] = None
    spreadsheet_id: Optional[str] = None
    worksheet_name: str
    last_synced_at: Optional[str] = None
    last_sync_status: Optional[str] = None
    last_sync_message: Optional[str] = None


@router.get("/config", response_model=SheetsConfigResponse)
def get_sheets_config(user_id: str = "default", db: Session = Depends(get_db)):
    """Retrieves current dynamic Google Sheets configuration and connection status."""
    service = DynamicGoogleSheetsService(db)
    config = service.get_or_create_config(user_id=user_id)
    return SheetsConfigResponse(
        is_connected=config.is_connected,
        connected_email=config.connected_email,
        connected_account_name=config.connected_account_name,
        spreadsheet_url=config.spreadsheet_url,
        spreadsheet_id=config.spreadsheet_id,
        worksheet_name=config.worksheet_name or "EventDhara Catalog",
        last_synced_at=config.last_synced_at.isoformat() if config.last_synced_at else None,
        last_sync_status=config.last_sync_status,
        last_sync_message=config.last_sync_message
    )


@router.post("/config", response_model=SheetsConfigResponse)
def update_sheets_config(
    payload: SheetsConfigUpdateRequest,
    user_id: str = "default",
    db: Session = Depends(get_db)
):
    """Updates user Google Spreadsheet URL and Worksheet / Tab name."""
    service = DynamicGoogleSheetsService(db)
    res = service.update_config(
        spreadsheet_url=payload.spreadsheet_url,
        worksheet_name=payload.worksheet_name,
        user_id=user_id
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Invalid spreadsheet configuration"))

    config = service.get_or_create_config(user_id=user_id)
    return SheetsConfigResponse(
        is_connected=config.is_connected,
        connected_email=config.connected_email,
        connected_account_name=config.connected_account_name,
        spreadsheet_url=config.spreadsheet_url,
        spreadsheet_id=config.spreadsheet_id,
        worksheet_name=config.worksheet_name or "EventDhara Catalog",
        last_synced_at=config.last_synced_at.isoformat() if config.last_synced_at else None,
        last_sync_status=config.last_sync_status,
        last_sync_message=config.last_sync_message
    )


@router.get("/oauth/authorize")
def get_oauth_authorize_url(
    user_id: str = "default",
    redirect_uri: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Generates Google OAuth 2.0 authorization URL for connecting a user Google Account."""
    service = DynamicGoogleSheetsService(db)
    res = service.generate_auth_url(user_id=user_id, redirect_uri=redirect_uri)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "OAuth initialization failed"))
    return res


@router.get("/oauth/callback")
def handle_oauth_callback(
    code: Optional[str] = None,
    error: Optional[str] = None,
    state: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Handles Google OAuth redirect callback, exchanges token, and informs the frontend.
    Supports both direct page redirection and OAuth popup windows.
    """
    if error:
        logger.warning("Google OAuth error received: %s", error)
        return HTMLResponse(
            f"""<!DOCTYPE html><html><body>
            <h3>Google Authentication Failed</h3>
            <p>{error}</p>
            <script>
              if (window.opener) {{
                window.opener.postMessage({{ type: 'GOOGLE_SHEETS_AUTH_ERROR', error: '{error}' }}, '*');
                setTimeout(() => window.close(), 2500);
              }}
            </script>
            </body></html>""",
            status_code=400
        )

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code from Google OAuth")

    service = DynamicGoogleSheetsService(db)
    # Reconstruct redirect_uri from current request if necessary
    request_redirect = str(request.url.remove_query_params(["code", "state", "scope"])) if request else None

    res = service.handle_oauth_callback(code=code, state=state, redirect_uri=request_redirect)
    if not res.get("success"):
        return HTMLResponse(
            f"""<!DOCTYPE html><html><body>
            <h3>Google Authentication Failed</h3>
            <p>{res.get('message')}</p>
            <script>
              if (window.opener) {{
                window.opener.postMessage({{ type: 'GOOGLE_SHEETS_AUTH_ERROR', error: '{res.get("message")}' }}, '*');
                setTimeout(() => window.close(), 3000);
              }}
            </script>
            </body></html>""",
            status_code=400
        )

    email = res.get("email", "Connected Account")

    # Return script that alerts opener popup and auto-closes, or redirects
    html = f"""<!DOCTYPE html>
<html>
<head>
  <title>EventDhara AI - Google Connected</title>
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #0F172A; color: #F8FAFC; text-align: center; }}
    .card {{ background: #1E293B; border: 1px solid #334155; padding: 2.5rem; border-radius: 1rem; max-width: 400px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }}
    .icon {{ width: 50px; height: 50px; background: #10B981; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 1.25rem; font-size: 1.5rem; font-weight: bold; }}
    h2 {{ margin: 0 0 0.5rem; font-size: 1.25rem; }}
    p {{ color: #94A3B8; font-size: 0.9rem; margin: 0 0 1.5rem; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✓</div>
    <h2>Google Account Connected</h2>
    <p>Authenticated as <strong>{email}</strong>. This window will close automatically.</p>
  </div>
  <script>
    if (window.opener) {{
      window.opener.postMessage({{ type: 'GOOGLE_SHEETS_AUTH_SUCCESS', email: '{email}' }}, '*');
      setTimeout(() => window.close(), 1500);
    }} else {{
      setTimeout(() => {{
        window.location.href = '/metadata?sheets_connected=true';
      }}, 2000);
    }}
  </script>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=200)


@router.post("/test")
def test_sheets_connection(user_id: str = "default", db: Session = Depends(get_db)):
    """
    Validates connection to the configured Google Spreadsheet and verifies that
    the connected user has write/Editor permissions.
    """
    service = DynamicGoogleSheetsService(db)
    res = service.test_connection(user_id=user_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Connection test failed"))
    return res


@router.post("/disconnect")
def disconnect_sheets(user_id: str = "default", db: Session = Depends(get_db)):
    """Disconnects connected Google account and resets spreadsheet configuration."""
    service = DynamicGoogleSheetsService(db)
    return service.disconnect(user_id=user_id)


@router.post("/sync")
def sync_metadata_to_sheets(
    payload: Optional[SheetsSyncRequest] = None,
    user_id: str = "default",
    db: Session = Depends(get_db)
):
    """
    Appends structured metadata rows into the user's connected Google Spreadsheet
    with 10 required columns, automatic headers, Hindi/English text support, and duplicate prevention.
    """
    service = DynamicGoogleSheetsService(db)
    image_ids = payload.image_ids if payload else None
    cat_id = payload.category_id if payload else None

    res = service.append_metadata(image_ids=image_ids, category_id=cat_id, user_id=user_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Google Sheets append failed"))
    return res
