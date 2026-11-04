import pytest
from fastapi.testclient import TestClient
from app.main import app

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
    # Every node has cloud_path and sync stats
    first = tree[0]
    assert "cloud_path" in first
    assert "total_approved" in first
    assert "synced_count" in first


def test_google_sheets_export_endpoint():
    res = client.post(
        "/api/v1/google-drive/export-sheets",
        json={"status": "APPROVED", "title_prefix": "Pytest Test Catalog"}
    )
    # Status code 200 (either published live to Drive as Google Sheet or local saved)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["total_rows"] >= 0
    assert "status" in data


def test_gemini_api_connection_diagnostics():
    res = client.post("/api/v1/settings/test-gemini")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "message" in data
    # Status is one of the recognized diagnostic states
    assert data["status"] in ["CONNECTED", "QUOTA_OR_BILLING_REQUIRED", "INVALID_KEY", "NOT_CONFIGURED"]
