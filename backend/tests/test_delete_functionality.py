import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.image import ImageItem
from app.models.audit import AuditLog

client = TestClient(app)


def test_single_image_deletion_and_audit():
    # 1. Upload a single test image
    img = Image.new("RGB", (900, 700), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    upload_res = client.post(
        "/api/v1/uploads/images",
        files={"files": ("delete_test_photo.jpg", buf.getvalue(), "image/jpeg")}
    )
    assert upload_res.status_code == 200
    items = upload_res.json()["processed_items"]
    assert len(items) > 0
    img_id = items[0]["id"]

    # Verify exists
    get_res = client.get(f"/api/v1/images/{img_id}")
    assert get_res.status_code == 200

    # 2. Delete the image
    del_res = client.delete(f"/api/v1/images/{img_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # 3. Verify 404 on subsequent get
    assert client.get(f"/api/v1/images/{img_id}").status_code == 404

    # 4. Verify audit log exists
    db = SessionLocal()
    audit = db.query(AuditLog).filter(AuditLog.action == "DELETE_IMAGE", AuditLog.image_id == img_id).first()
    assert audit is not None
    assert f"#{img_id}" in audit.details
    db.close()


def test_delete_nonexistent_image_returns_404():
    res = client.delete("/api/v1/images/9999999")
    assert res.status_code == 404


def test_bulk_deletion():
    # Upload 2 images
    img1 = Image.new("RGB", (900, 700), color=(120, 130, 140))
    buf1 = io.BytesIO()
    img1.save(buf1, format="JPEG")

    img2 = Image.new("RGB", (900, 700), color=(150, 160, 170))
    buf2 = io.BytesIO()
    img2.save(buf2, format="JPEG")

    upload_res = client.post(
        "/api/v1/uploads/images",
        files=[
            ("files", ("bulk_del_1.jpg", buf1.getvalue(), "image/jpeg")),
            ("files", ("bulk_del_2.jpg", buf2.getvalue(), "image/jpeg")),
        ]
    )
    assert upload_res.status_code == 200
    items = upload_res.json()["processed_items"]
    ids = [i["id"] for i in items]

    # Bulk delete
    bulk_res = client.post("/api/v1/images/bulk-action", json={"image_ids": ids, "action": "DELETE"})
    assert bulk_res.status_code == 200
    assert bulk_res.json()["success_count"] == len(ids)

    # Verify both deleted
    for i_id in ids:
        assert client.get(f"/api/v1/images/{i_id}").status_code == 404
