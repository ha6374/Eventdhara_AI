import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import Base, engine
from app.core.security import encrypt_token, decrypt_token
from app.services.dynamic_sheets_service import DynamicGoogleSheetsService

# Ensure database tables exist
Base.metadata.create_all(bind=engine)

client = TestClient(app)


def test_fernet_token_encryption_and_decryption():
    raw_token = "ya29.a0AfH6SMD_sample_google_access_token_12345"
    encrypted = encrypt_token(raw_token)
    assert encrypted is not None
    assert encrypted != raw_token
    assert len(encrypted) > len(raw_token)

    decrypted = decrypt_token(encrypted)
    assert decrypted == raw_token


def test_spreadsheet_id_regex_extractor():
    # Standard URL
    url1 = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0"
    assert DynamicGoogleSheetsService.extract_spreadsheet_id(url1) == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"

    # View mode URL
    url2 = "https://docs.google.com/spreadsheets/d/1hOscz4DkstWCZVZfc_K85VpLyaRy3jGitzFfjyynOUM/view"
    assert DynamicGoogleSheetsService.extract_spreadsheet_id(url2) == "1hOscz4DkstWCZVZfc_K85VpLyaRy3jGitzFfjyynOUM"

    # Raw ID
    raw_id = "1hOscz4DkstWCZVZfc_K85VpLyaRy3jGitzFfjyynOUM"
    assert DynamicGoogleSheetsService.extract_spreadsheet_id(raw_id) == "1hOscz4DkstWCZVZfc_K85VpLyaRy3jGitzFfjyynOUM"

    # Invalid URL
    assert DynamicGoogleSheetsService.extract_spreadsheet_id("https://google.com/search") is None
    assert DynamicGoogleSheetsService.extract_spreadsheet_id("") is None


def test_sheets_config_endpoints():
    # 1. Get initial config
    resp = client.get("/api/v1/sheets/config?user_id=test_operator")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_connected" in data
    assert "worksheet_name" in data

    # 2. Update config with valid spreadsheet URL
    update_payload = {
        "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit",
        "worksheet_name": "Wedding Catalog"
    }
    resp_update = client.post("/api/v1/sheets/config?user_id=test_operator", json=update_payload)
    assert resp_update.status_code == 200
    updated_data = resp_update.json()
    assert updated_data["spreadsheet_id"] == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
    assert updated_data["worksheet_name"] == "Wedding Catalog"

    # 3. Update with invalid URL returns 400
    resp_invalid = client.post("/api/v1/sheets/config?user_id=test_operator", json={"spreadsheet_url": "not-a-valid-url"})
    assert resp_invalid.status_code == 400

    # 4. Test connection without OAuth tokens returns 400 with helpful detail
    resp_test = client.post("/api/v1/sheets/test?user_id=test_operator")
    assert resp_test.status_code == 400
    assert "not connected" in resp_test.json()["detail"].lower()

    # 5. Sync without OAuth tokens returns 400
    resp_sync = client.post("/api/v1/sheets/sync?user_id=test_operator", json={})
    assert resp_sync.status_code == 400

    # 6. Disconnect endpoint resets status
    resp_disc = client.post("/api/v1/sheets/disconnect?user_id=test_operator")
    assert resp_disc.status_code == 200
    assert resp_disc.json()["success"] is True
