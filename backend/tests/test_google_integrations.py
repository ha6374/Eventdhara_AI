import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.sheets_service import GoogleSheetsService

client = TestClient(app)


def test_google_drive_status_endpoint():
    res = client.get("/api/v1/google-drive/status")
    assert res.status_code == 200
    data = res.json()
    assert "connected" in data
    assert "status" in data
    assert "total_approved" in data
    assert "synced_to_drive" in data


def test_google_drive_folders_endpoint():
    res = client.get("/api/v1/google-drive/folders")
    assert res.status_code == 200
    tree = res.json()
    assert isinstance(tree, list)
    assert len(tree) > 0
    first = tree[0]
    assert "cloud_path" in first
    assert "total_approved" in first
    assert "synced_count" in first


def test_google_sheets_export_endpoint(monkeypatch):

    class FakeRequest:
        def execute(self):
            return {
                "id": "pytest_fake_sheet_id",
                "name": "Pytest Test Catalog",
                "webViewLink": "https://docs.google.com/spreadsheets/d/pytest_fake_sheet_id/edit"
            }

    class FakeFiles:
        def create(self, **kwargs):
            return FakeRequest()

    class FakeDrive:
        def files(self):
            return FakeFiles()

    monkeypatch.setattr(
        GoogleSheetsService,
        "_get_drive_client",
        lambda self: FakeDrive()
    )

    res = client.post(
        "/api/v1/google-drive/export-sheets",
        json={"status": "APPROVED", "title_prefix": "Pytest Test Catalog"}
    )

    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["total_rows"] >= 0
    assert data["status"] == "PUBLISHED"
    assert data["sheet_id"] == "pytest_fake_sheet_id"


def test_gemini_api_connection_diagnostics():
    res = client.post("/api/v1/settings/test-gemini")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "message" in data
    assert data["status"] in [
        "CONNECTED",
        "QUOTA_OR_BILLING_REQUIRED",
        "INVALID_KEY",
        "NOT_CONFIGURED"
    ]
