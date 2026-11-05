import io
import zipfile
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_empty_zip_archive():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        pass  # Empty archive
    buf.seek(0)

    res = client.post(
        "/api/v1/uploads/zip",
        files={"file": ("empty.zip", buf.getvalue(), "application/zip")}
    )
    assert res.status_code == 200
    assert res.json()["valid_images"] == 0


def test_corrupted_zip_archive_returns_400():
    fake_corrupted_bytes = b"PK\x03\x04ThisIsNotAValidZipArchiveGarbageBytes"
    res = client.post(
        "/api/v1/uploads/zip",
        files={"file": ("corrupt.zip", fake_corrupted_bytes, "application/zip")}
    )
    assert res.status_code == 400
    assert "Corrupted or invalid ZIP" in res.json()["detail"]


def test_unsupported_file_format_rejected():
    res = client.post(
        "/api/v1/uploads/images",
        files={"files": ("malicious.exe", b"MZDummyBinary", "application/octet-stream")}
    )
    assert res.status_code == 200
    assert res.json()["invalid_files"] >= 1
    assert res.json()["valid_images"] == 0


def test_severely_underexposed_dark_image():
    # Mean pixel value ~ 5-15 (very dark) with spatial structure so pHash does not collapse to zero
    import numpy as np
    import uuid, time
    from app.core.database import SessionLocal
    from app.models.image import ImageItem
    from app.services.category_storage import remove_image_from_storage

    # Ensure clean slate from any prior test executions
    _db = SessionLocal()
    try:
        for old in _db.query(ImageItem).filter(ImageItem.original_filename.ilike('%night_dark%')).all():
            remove_image_from_storage(old)
            _db.delete(old)
        _db.commit()
    finally:
        _db.close()

    seed = int(time.time() * 1000) % (2**31 - 1)
    rng = np.random.RandomState(seed)
    dark_arr = np.zeros((700, 900, 3), dtype=np.uint8)
    # Add dark shapes (values 10-25)
    dark_arr[100:300, 100:400] = rng.randint(12, 22)
    dark_arr[400:600, 500:800] = rng.randint(15, 25)
    dark_arr[50:150, 700:850] = rng.randint(10, 20)
    dark_arr = np.clip(dark_arr + rng.randint(0, 5, dark_arr.shape, dtype=np.uint8), 0, 28)

    dark_img = Image.fromarray(dark_arr)
    buf = io.BytesIO()
    dark_img.save(buf, format="JPEG", quality=95)

    test_fn = f"night_dark_{uuid.uuid4().hex[:8]}.jpg"
    try:
        res = client.post(
            "/api/v1/uploads/images",
            files={"files": (test_fn, buf.getvalue(), "image/jpeg")}
        )
        assert res.status_code == 200
        items = res.json()["processed_items"]
        assert len(items) > 0
        # Should be rejected due to severe underexposure
        assert items[0]["status"] == "REJECTED"
        assert "dark" in items[0]["rejection_reason"].lower() or "underexposure" in items[0]["rejection_reason"].lower()
    finally:
        _db2 = SessionLocal()
        try:
            created = _db2.query(ImageItem).filter(ImageItem.original_filename == test_fn).first()
            if created:
                remove_image_from_storage(created)
                _db2.delete(created)
                _db2.commit()
        finally:
            _db2.close()


def test_mobile_screenshot_aspect_ratio_rejection():
    # Aspect ratio > 2.08: e.g. 1080x2400 (aspect ratio 2.22) with noise for > 50KB file size
    import numpy as np
    import uuid, time
    seed = (int(time.time() * 1000) + 123) % (2**31 - 1)
    rng = np.random.RandomState(seed)
    ss_arr = rng.randint(60, 200, (2400, 1080, 3), dtype=np.uint8)
    screenshot_img = Image.fromarray(ss_arr)
    buf = io.BytesIO()
    screenshot_img.save(buf, format="JPEG", quality=90)

    test_fn = f"screenshot_{uuid.uuid4().hex[:8]}.jpg"
    res = client.post(
        "/api/v1/uploads/images",
        files={"files": (test_fn, buf.getvalue(), "image/jpeg")}
    )
    assert res.status_code == 200
    items = res.json()["processed_items"]
    assert len(items) > 0
    assert items[0]["status"] == "REJECTED"
    assert "screenshot" in items[0]["rejection_reason"].lower()


def test_duplicate_image_detection():
    # Create unique textured image with size > 50KB
    import numpy as np
    import uuid, time
    seed = (int(time.time() * 1000) + 456) % (2**31 - 1)
    rng = np.random.RandomState(seed)
    dup_arr = rng.randint(50, 200, (720, 920, 3), dtype=np.uint8)
    img = Image.fromarray(dup_arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    raw_bytes = buf.getvalue()

    run_id = uuid.uuid4().hex[:8]
    # Upload first time
    res1 = client.post(
        "/api/v1/uploads/images",
        files={"files": (f"orig_{run_id}.jpg", raw_bytes, "image/jpeg")}
    )
    assert res1.status_code == 200
    first_item = res1.json()["processed_items"][0]

    # Upload second time (exact duplicate)
    res2 = client.post(
        "/api/v1/uploads/images",
        files={"files": (f"dup_{run_id}.jpg", raw_bytes, "image/jpeg")}
    )
    assert res2.status_code == 200
    second_item = res2.json()["processed_items"][0]

    assert second_item["status"] == "DUPLICATE"
    assert second_item["is_duplicate"] is True
    assert second_item["duplicate_of_id"] == first_item["id"]


def test_nested_folders_and_duplicate_filenames_in_zip():
    # ZIP with nested subfolders and identical basenames
    import numpy as np
    rng = np.random.RandomState(46)
    arr1 = rng.randint(60, 200, (700, 900, 3), dtype=np.uint8)
    img1 = Image.fromarray(arr1)
    buf1 = io.BytesIO()
    img1.save(buf1, format="JPEG", quality=90)

    arr2 = rng.randint(60, 200, (700, 900, 3), dtype=np.uint8)
    img2 = Image.fromarray(arr2)
    buf2 = io.BytesIO()
    img2.save(buf2, format="JPEG", quality=90)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Nested/FolderA/decoration_photo.jpg", buf1.getvalue())
        zf.writestr("Nested/FolderB/decoration_photo.jpg", buf2.getvalue())
    zip_buf.seek(0)

    res = client.post(
        "/api/v1/uploads/zip",
        files={"file": ("nested_duplicates.zip", zip_buf.getvalue(), "application/zip")}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["valid_images"] == 2
    assert len(data["processed_items"]) == 2
    # Ensure both files were saved with distinct, non-overwritten filenames
    assert data["processed_items"][0]["filename"] != data["processed_items"][1]["filename"]


def test_corrupted_image_file_rejected():
    # File with JPEG header but corrupted binary data (>50KB)
    corrupted_data = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 60000
    res = client.post(
        "/api/v1/uploads/images",
        files={"files": ("corrupt_decor.jpg", corrupted_data, "image/jpeg")}
    )
    assert res.status_code == 200
    items = res.json()["processed_items"]
    assert len(items) > 0
    assert items[0]["status"] == "REJECTED"
    assert "corrupt" in items[0]["rejection_reason"].lower() or "invalid" in items[0]["rejection_reason"].lower()


def test_gemini_missing_api_key_resilient_fallback():
    from app.services.gemini_service import GeminiService
    service = GeminiService()
    service.api_key = ""
    service.client = None

    import numpy as np
    import tempfile, os
    rng = np.random.RandomState(47)
    arr = rng.randint(60, 200, (700, 900, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img.save(tmp.name, format="JPEG", quality=90)
        tmp_path = tmp.name

    try:
        result = service.classify_image(tmp_path, uploaded_category="Wedding Decoration")
        assert "predicted_category" in result
        assert "confidence_score" in result
        assert "approval_status" in result
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

