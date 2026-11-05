import io
import os
import zipfile
import tracemalloc
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.image import ImageItem
from app.models.batch import UploadBatch
from app.services.category_storage import remove_image_from_storage

client = TestClient(app)


def test_zip_exceeding_max_files_limit():
    """Validates that a ZIP archive with more entries than ZIP_MAX_FILES is safely rejected with HTTP 400."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Create ZIP_MAX_FILES + 5 empty entries
        for i in range(settings.ZIP_MAX_FILES + 5):
            zf.writestr(f"entry_{i}.jpg", b"fake_data")
    buf.seek(0)

    res = client.post(
        "/api/v1/uploads/zip",
        files={"file": ("too_many_files.zip", buf.getvalue(), "application/zip")}
    )
    assert res.status_code == 400
    assert "exceeding the maximum allowed limit" in res.json()["detail"]

    # Verify that failed batch record is safely persisted to database with status FAILED
    db = SessionLocal()
    try:
        latest_batch = db.query(UploadBatch).order_by(UploadBatch.created_at.desc()).first()
        assert latest_batch is not None
        assert latest_batch.status == "FAILED"
        assert "exceeding the maximum allowed limit" in latest_batch.error_message
        assert latest_batch.completed_at is not None
    finally:
        db.close()


def test_zip_exceeding_entry_size_limit(monkeypatch):
    """Validates that a ZIP entry whose uncompressed size exceeds ZIP_MAX_FILE_SIZE_MB is rejected with HTTP 400."""
    import numpy as np
    # Temporarily lower limit to 0.01 MB (10 KB) to test entry size rejection
    monkeypatch.setattr(settings, "ZIP_MAX_FILE_SIZE_MB", 0.01)

    rng = np.random.RandomState(42)
    arr = rng.randint(40, 220, (650, 850, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    img_buf = io.BytesIO()
    img.save(img_buf, format="JPEG", quality=90)  # > 50KB

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("oversized.jpg", img_buf.getvalue())
    buf.seek(0)

    res = client.post(
        "/api/v1/uploads/zip",
        files={"file": ("oversized_entry.zip", buf.getvalue(), "application/zip")}
    )
    assert res.status_code == 400
    assert "exceeds maximum allowed limit" in res.json()["detail"]


def test_small_zip_valid_upload():
    """Validates upload and successful extraction of a small ZIP archive."""
    # Generate 2 valid images (> 50KB, >= 800x600)
    import numpy as np
    rng = np.random.RandomState(42)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx in range(2):
            arr = rng.randint(40, 220, (650, 850, 3), dtype=np.uint8)
            img = Image.fromarray(arr)
            img_buf = io.BytesIO()
            img.save(img_buf, format="JPEG", quality=90)
            zf.writestr(f"Wedding/photo_{idx}.jpg", img_buf.getvalue())
    buf.seek(0)

    res = client.post(
        "/api/v1/uploads/zip",
        files={"file": ("small_test.zip", buf.getvalue(), "application/zip")}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["valid_images"] == 2
    assert data["invalid_files"] == 0

    # Clean up test rows
    db = SessionLocal()
    try:
        for item in data["processed_items"]:
            row = db.query(ImageItem).filter(ImageItem.id == item["id"]).first()
            if row:
                remove_image_from_storage(row)
                db.delete(row)
        db.commit()
    finally:
        db.close()


def test_zip_memory_bounded_under_batch_processing():
    """
    Simulates sequential batch processing of multiple images inside a ZIP archive
    and profiles Python memory using tracemalloc to ensure RAM stays bounded.
    """
    import numpy as np
    rng = np.random.RandomState(99)

    # Create a batch of 15 valid images
    batch_count = 15
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx in range(batch_count):
            arr = rng.randint(50, 210, (650, 850, 3), dtype=np.uint8)
            img = Image.fromarray(arr)
            img_buf = io.BytesIO()
            img.save(img_buf, format="JPEG", quality=85)
            zf.writestr(f"Reception/batch_img_{idx}_{rng.randint(1000, 9999)}.jpg", img_buf.getvalue())
    buf.seek(0)

    tracemalloc.start()
    mem_before, _ = tracemalloc.get_traced_memory()

    res = client.post(
        "/api/v1/uploads/zip",
        files={"file": ("batch_memory_test.zip", buf.getvalue(), "application/zip")}
    )

    mem_current, mem_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert res.status_code == 200
    data = res.json()
    assert data["valid_images"] == batch_count

    # Peak memory allocated by Python should remain well bounded (< 80 MB for 15 full pipeline evaluations)
    peak_mb = mem_peak / (1024 * 1024)
    assert peak_mb < 80.0, f"Peak memory {peak_mb:.1f} MB exceeded threshold"

    # Clean up test rows from database and disk
    db = SessionLocal()
    try:
        # Verify UploadBatch persistence in database
        batch_record = db.query(UploadBatch).filter(UploadBatch.id == data["batch_id"]).first()
        assert batch_record is not None
        assert batch_record.status == "COMPLETED"
        assert batch_record.valid_files == batch_count
        assert batch_record.invalid_files == 0
        assert batch_record.total_files == batch_count
        assert batch_record.error_message is None
        assert batch_record.completed_at is not None

        for item in data["processed_items"]:
            row = db.query(ImageItem).filter(ImageItem.id == item["id"]).first()
            if row:
                remove_image_from_storage(row)
                db.delete(row)
        db.commit()
    finally:
        db.close()
