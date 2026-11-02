import pytest
from app.api.v1.endpoints.uploads import is_safe_zip_path
from app.core.database import SessionLocal
from app.models.image import ImageItem
from app.models.audit import AuditLog
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_anti_zipslip_path_traversal_detection():
    target_dir = "C:\\Users\\HARSH\\eventdhara-ai\\storage\\extracted\\test_batch"

    # Malicious traversal paths
    assert not is_safe_zip_path(target_dir, "../../windows/system32/cmd.exe")
    assert not is_safe_zip_path(target_dir, "../../../etc/passwd")
    assert not is_safe_zip_path(target_dir, "..\\..\\evil.jpg")

    # Safe sub-paths
    assert is_safe_zip_path(target_dir, "images/balloon1.jpg")
    assert is_safe_zip_path(target_dir, "decor.png")


def test_secrets_not_exposed_in_settings_endpoint():
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    data = response.json()
    # Confirm secret keys and passwords are NEVER exposed in plain text
    assert "DATABASE_URL" not in data
    assert "123456" not in str(data)
    assert "secret_key" not in data
    # Only boolean indication is exposed
    assert "gemini_api_key_configured" in data


def test_audit_log_created_on_manual_status_change():
    db = SessionLocal()
    # Find an image
    img = db.query(ImageItem).first()
    if img:
        initial_log_count = db.query(AuditLog).filter(AuditLog.image_id == img.id).count()

        # Update status via API
        response = client.patch(
            f"/api/v1/images/{img.id}/status",
            json={"status": "REVIEW_REQUIRED", "reason": "Security compliance test audit"}
        )
        assert response.status_code == 200

        # Verify new audit log row exists
        new_log_count = db.query(AuditLog).filter(AuditLog.image_id == img.id).count()
        assert new_log_count > initial_log_count
    db.close()
