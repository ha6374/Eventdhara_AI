import io
import os
import json
import uuid
import pytest
import numpy as np
from PIL import Image
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.image import ImageItem
from app.models.category import Category
from app.models.metadata import ImageMetadata
from app.services.gemini_service import gemini_service
from app.services.export_service import ExportService

client = TestClient(app)


def create_test_image_file(width=850, height=650, fmt="JPEG"):
    seed = int.from_bytes(os.urandom(4), "big")
    rng = np.random.RandomState(seed)
    arr = rng.randint(40, 220, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=90)
    return buf.getvalue()


def upload_and_approve_image(filename_prefix="test_img", fmt="JPEG", mime="image/jpeg"):
    content = create_test_image_file(fmt=fmt)
    unique_fn = f"{filename_prefix}_{uuid.uuid4().hex[:8]}.{fmt.lower()}"
    res = client.post(
        "/api/v1/uploads/images",
        files={"files": (unique_fn, content, mime)}
    )
    assert res.status_code == 200, f"Upload failed: {res.text}"
    img_id = res.json()["processed_items"][0]["id"]

    # Approve image
    app_res = client.patch(f"/api/v1/images/{img_id}/status", json={"status": "APPROVED"})
    assert app_res.status_code == 200
    return img_id


def get_mock_gemini_success_response(name="Royal Marigold Floral Mandap Setup"):
    mock_resp = MagicMock()
    mock_data = {
        "name": name,
        "short_description": "Exclusive traditional wedding mandap with hand-woven yellow marigold garlands.",
        "long_description": "An opulent celebration setup featuring dense marigold hangings, brass accents, and structured drapery for grand ceremonies.",
        "inclusion": [
            "Four-pillar mandap framework",
            "Fresh yellow marigold floral hangings",
            "Traditional backdrop draping",
            "Low seating ceremonial carpet"
        ],
        "faq": [
            {"question": "Can this setup be customized for indoor halls?", "answer": "Yes, height can be adjusted to hall ceilings."},
            {"question": "Are flowers fresh?", "answer": "Yes, fresh marigolds sourced on the event day."}
        ],
        "note": "Requires minimum 12ft x 12ft cleared area.",
        "keywords": ["mandap decoration", "marigold wedding", "traditional decor"],
        "tags": ["Wedding", "Mandap", "Marigold", "Traditional"]
    }
    mock_resp.text = json.dumps(mock_data)
    return mock_resp


# =========================================================================
# TEST 1: Gemini API successful response
# =========================================================================
def test_1_gemini_api_successful_response():
    img_id = upload_and_approve_image("test1_success")

    mock_resp = get_mock_gemini_success_response("Grand Royal Mandap Decor #1")
    with patch.object(gemini_service.client.models, "generate_content", return_value=mock_resp):
        res = client.post(f"/api/v1/metadata/generate/{img_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Grand Royal Mandap Decor #1"
        assert len(data["short_description"]) > 10
        assert len(data["long_description"]) > 20
        assert len(data["inclusion"]) == 4
        assert len(data["faq"]) == 2
        assert len(data["keywords"]) == 3
        assert len(data["tags"]) == 4
        assert data["processing_status"] == "COMPLETED"

    # Verify DB state
    db = SessionLocal()
    db_img = db.query(ImageItem).filter(ImageItem.id == img_id).first()
    assert db_img.metadata_status == "COMPLETED"
    db_meta = db.query(ImageMetadata).filter(ImageMetadata.image_id == img_id).first()
    assert db_meta is not None
    assert db_meta.name == "Grand Royal Mandap Decor #1"
    db.close()


# =========================================================================
# TEST 2: Gemini API returns 429
# =========================================================================
def test_2_gemini_api_returns_429():
    img_id = upload_and_approve_image("test2_429")

    with patch.object(gemini_service.client.models, "generate_content", side_effect=Exception("429 RESOURCE_EXHAUSTED: Quota exceeded")):
        res = client.post(f"/api/v1/metadata/generate/{img_id}")
        assert res.status_code in (400, 502)
        assert "429" in res.text or "quota" in res.text.lower()

    # Verify DB: status FAILED, NO metadata record
    db = SessionLocal()
    db_img = db.query(ImageItem).filter(ImageItem.id == img_id).first()
    assert db_img.metadata_status == "FAILED"
    db_meta = db.query(ImageMetadata).filter(ImageMetadata.image_id == img_id).first()
    assert db_meta is None
    db.close()


# =========================================================================
# TEST 3: Gemini API returns 403
# =========================================================================
def test_3_gemini_api_returns_403():
    img_id = upload_and_approve_image("test3_403")

    with patch.object(gemini_service.client.models, "generate_content", side_effect=Exception("403 PERMISSION_DENIED: Billing required")):
        res = client.post(f"/api/v1/metadata/generate/{img_id}")
        assert res.status_code in (400, 502)
        assert "403" in res.text or "permission" in res.text.lower() or "billing" in res.text.lower()

    db = SessionLocal()
    db_img = db.query(ImageItem).filter(ImageItem.id == img_id).first()
    assert db_img.metadata_status == "FAILED"
    db_meta = db.query(ImageMetadata).filter(ImageMetadata.image_id == img_id).first()
    assert db_meta is None
    db.close()


# =========================================================================
# TEST 4: Gemini API returns 503
# =========================================================================
def test_4_gemini_api_returns_503():
    img_id = upload_and_approve_image("test4_503")

    with patch.object(gemini_service.client.models, "generate_content", side_effect=Exception("503 UNAVAILABLE: Model overloaded")):
        res = client.post(f"/api/v1/metadata/generate/{img_id}")
        assert res.status_code in (400, 502)
        assert "503" in res.text or "unavailable" in res.text.lower()

    db = SessionLocal()
    db_img = db.query(ImageItem).filter(ImageItem.id == img_id).first()
    assert db_img.metadata_status == "FAILED"
    db_meta = db.query(ImageMetadata).filter(ImageMetadata.image_id == img_id).first()
    assert db_meta is None
    db.close()


# =========================================================================
# TEST 5: Run Generate Metadata twice for the same image
# =========================================================================
def test_5_generate_twice_skips_second_call():
    img_id = upload_and_approve_image("test5_duplicate_check")

    mock_resp = get_mock_gemini_success_response("First Run Title")
    with patch.object(gemini_service.client.models, "generate_content", return_value=mock_resp) as mock_gen:
        # First call: generates metadata
        res1 = client.post(f"/api/v1/metadata/generate/{img_id}")
        assert res1.status_code == 200
        assert mock_gen.call_count == 1
        meta1 = res1.json()
        assert meta1["name"] == "First Run Title"

        # Second call: MUST skip Gemini call
        res2 = client.post(f"/api/v1/metadata/generate/{img_id}")
        assert res2.status_code == 200
        # Call count MUST remain 1!
        assert mock_gen.call_count == 1
        meta2 = res2.json()
        assert meta2["name"] == "First Run Title"
        assert meta2.get("message") == "Metadata already generated"
        assert res2.headers.get("x-metadata-notice") == "Metadata already generated"

    # Verify only 1 record exists in DB
    db = SessionLocal()
    meta_records = db.query(ImageMetadata).filter(ImageMetadata.image_id == img_id).all()
    assert len(meta_records) == 1
    db.close()


# =========================================================================
# TEST 6: Two simultaneous requests for the same image
# =========================================================================
def test_6_simultaneous_requests_prevented():
    img_id = upload_and_approve_image("test6_concurrency")

    db = SessionLocal()
    img = db.query(ImageItem).filter(ImageItem.id == img_id).first()
    # Simulate first request currently in PROCESSING state
    img.metadata_status = "PROCESSING"
    db.commit()
    db.close()

    # Second simultaneous request should be blocked with 409 Conflict
    with patch.object(gemini_service.client.models, "generate_content") as mock_gen:
        res = client.post(f"/api/v1/metadata/generate/{img_id}")
        assert res.status_code == 409
        assert "in progress" in res.json()["detail"].lower()
        # Gemini should NEVER be called
        assert mock_gen.call_count == 0


# =========================================================================
# TEST 7: Regenerate existing metadata
# =========================================================================
def test_7_regenerate_existing_metadata():
    img_id = upload_and_approve_image("test7_regen_success")

    # Step 1: Generate initial metadata
    mock_resp1 = get_mock_gemini_success_response("Initial Mandap Decor")
    with patch.object(gemini_service.client.models, "generate_content", return_value=mock_resp1):
        res1 = client.post(f"/api/v1/metadata/generate/{img_id}")
        assert res1.status_code == 200
        orig_id = res1.json()["id"]

    # Step 2: Regenerate with fresh metadata
    mock_resp2 = get_mock_gemini_success_response("Freshly Regenerated Royal Canopy Setup")
    with patch.object(gemini_service.client.models, "generate_content", return_value=mock_resp2):
        res2 = client.post(f"/api/v1/metadata/regenerate/{img_id}")
        assert res2.status_code == 200
        regen_data = res2.json()
        assert regen_data["id"] == orig_id
        assert regen_data["name"] == "Freshly Regenerated Royal Canopy Setup"

    # Verify DB: exactly 1 metadata record, updated
    db = SessionLocal()
    records = db.query(ImageMetadata).filter(ImageMetadata.image_id == img_id).all()
    assert len(records) == 1
    assert records[0].name == "Freshly Regenerated Royal Canopy Setup"
    db.close()


# =========================================================================
# TEST 8: Regenerate when Gemini fails
# =========================================================================
def test_8_regenerate_failure_preserves_old_metadata():
    img_id = upload_and_approve_image("test8_regen_fail")

    # Step 1: Generate initial metadata
    mock_resp1 = get_mock_gemini_success_response("Initial Protected Title")
    with patch.object(gemini_service.client.models, "generate_content", return_value=mock_resp1):
        res1 = client.post(f"/api/v1/metadata/generate/{img_id}")
        assert res1.status_code == 200
        orig_id = res1.json()["id"]

    # Step 2: Attempt regenerate with Gemini failure (500 Internal Error)
    with patch.object(gemini_service.client.models, "generate_content", side_effect=Exception("500 Internal Server Error")):
        res2 = client.post(f"/api/v1/metadata/regenerate/{img_id}")
        assert res2.status_code in (400, 502)
        assert "preserved" in res2.text.lower()

    # Verify DB: Old metadata is PRESERVED, status remains COMPLETED
    db = SessionLocal()
    db_img = db.query(ImageItem).filter(ImageItem.id == img_id).first()
    assert db_img.metadata_status == "COMPLETED"
    db_meta = db.query(ImageMetadata).filter(ImageMetadata.image_id == img_id).first()
    assert db_meta is not None
    assert db_meta.id == orig_id
    assert db_meta.name == "Initial Protected Title"
    db.close()


# =========================================================================
# TEST 9: Bulk generation
# =========================================================================
def test_9_bulk_generation_skips_completed_and_handles_failures():
    # Setup images:
    # img_comp: already COMPLETED
    img_comp = upload_and_approve_image("test9_comp")
    mock_resp = get_mock_gemini_success_response("Pre-completed Image")
    with patch.object(gemini_service.client.models, "generate_content", return_value=mock_resp):
        res = client.post(f"/api/v1/metadata/generate/{img_comp}")
        assert res.status_code == 200

    # img_pending: APPROVED and PENDING
    img_pending = upload_and_approve_image("test9_pending")

    # img_fail: APPROVED and FAILED
    img_fail = upload_and_approve_image("test9_failed")
    db = SessionLocal()
    db_img_fail = db.query(ImageItem).filter(ImageItem.id == img_fail).first()
    db_img_fail.metadata_status = "FAILED"
    db.commit()
    db.close()

    # Now run bulk generation with mock Gemini
    mock_bulk = get_mock_gemini_success_response("Bulk Generated Decor")
    with patch.object(gemini_service.client.models, "generate_content", return_value=mock_bulk) as mock_gen:
        bulk_res = client.post("/api/v1/metadata/bulk-generate")
        assert bulk_res.status_code == 200
        data = bulk_res.json()
        assert data["success"] is True
        assert data["completed"] >= 2  # At least pending and failed images processed
        assert data["skipped"] >= 1    # At least img_comp skipped

    # Verify DB states
    db = SessionLocal()
    for iid in [img_comp, img_pending, img_fail]:
        item = db.query(ImageItem).filter(ImageItem.id == iid).first()
        assert item.metadata_status == "COMPLETED"
        assert item.metadata_rel is not None
    db.close()


# =========================================================================
# TEST 10: Different images from the same category
# =========================================================================
def test_10_different_images_same_category_independent_metadata():
    # Create two images with different patterns
    img1_id = upload_and_approve_image("test10_img1")
    img2_id = upload_and_approve_image("test10_img2")

    resp1 = get_mock_gemini_success_response("Sunset Orange Marigold Canopy Setup")
    resp2 = get_mock_gemini_success_response("Cool Blue Hydrangea & Crystal Arch")

    # Call Gemini for img1
    with patch.object(gemini_service.client.models, "generate_content", return_value=resp1):
        res1 = client.post(f"/api/v1/metadata/generate/{img1_id}")
        assert res1.status_code == 200
        data1 = res1.json()

    # Call Gemini for img2
    with patch.object(gemini_service.client.models, "generate_content", return_value=resp2):
        res2 = client.post(f"/api/v1/metadata/generate/{img2_id}")
        assert res2.status_code == 200
        data2 = res2.json()

    assert data1["name"] == "Sunset Orange Marigold Canopy Setup"
    assert data2["name"] == "Cool Blue Hydrangea & Crystal Arch"
    assert data1["name"] != data2["name"]
    assert data1["image_id"] != data2["image_id"]


# =========================================================================
# TEST 11: Invalid image path or corrupt image
# =========================================================================
def test_11_corrupt_or_missing_image_fails_without_template():
    img_id = upload_and_approve_image("test11_corrupt")

    # Corrupt the file on disk
    db = SessionLocal()
    db_img = db.query(ImageItem).filter(ImageItem.id == img_id).first()
    file_path = db_img.file_path
    if not os.path.isabs(file_path):
        from app.core.config import settings
        file_path = os.path.abspath(os.path.join(settings.STORAGE_ROOT, "processed", db_img.filename))
    db.close()

    # Overwrite image with garbage non-image bytes
    with open(file_path, "wb") as f:
        f.write(b"NOT_A_VALID_IMAGE_DATA_GARBAGE_BYTES")

    # Attempt metadata generation: MUST fail, NOT fallback to template!
    res = client.post(f"/api/v1/metadata/generate/{img_id}")
    assert res.status_code in (400, 500)

    db = SessionLocal()
    reloaded_img = db.query(ImageItem).filter(ImageItem.id == img_id).first()
    assert reloaded_img.metadata_status == "FAILED"
    db_meta = db.query(ImageMetadata).filter(ImageMetadata.image_id == img_id).first()
    assert db_meta is None  # NO template or placeholder metadata created
    db.close()


# =========================================================================
# TEST 12: Verify Excel export
# =========================================================================
def test_12_verify_excel_export():
    img_id = upload_and_approve_image("test12_export")

    mock_resp = get_mock_gemini_success_response("Excel Export Verified Setup")
    with patch.object(gemini_service.client.models, "generate_content", return_value=mock_resp):
        res = client.post(f"/api/v1/metadata/generate/{img_id}")
        assert res.status_code == 200

    db = SessionLocal()
    export_svc = ExportService(db)
    export_file = export_svc.export_images_data(export_format="excel")
    assert os.path.exists(export_file)
    assert export_file.endswith(".xlsx")

    # Read back generated Excel with pandas
    import pandas as pd
    df = pd.read_excel(export_file)
    assert "Product Title" in df.columns
    assert "Short Description" in df.columns
    assert "Tags" in df.columns
    assert "Google Drive URL" in df.columns

    # Verify exported row for our image
    img_row = df[df["Image ID"] == img_id]
    assert len(img_row) == 1
    assert img_row.iloc[0]["Product Title"] == "Excel Export Verified Setup"
    assert "mandap" in img_row.iloc[0]["Short Description"].lower()
    db.close()


# =========================================================================
# TEST LIVE: Live Gemini API test verifying real error behavior
# =========================================================================
def test_live_gemini_error_handling_without_template_fallback():
    """
    Tests live Gemini API integration with actual credentials.
    Verifies that when live API fails (e.g. 403 billing/quota),
    it properly sets FAILED and NEVER creates fake template metadata.
    """
    img_id = upload_and_approve_image("test_live_error")

    # Calling without any mock will hit the live API
    res = client.post(f"/api/v1/metadata/generate/{img_id}")
    # Live API returns 403 / 502 / 400
    assert res.status_code in (400, 502)

    db = SessionLocal()
    db_img = db.query(ImageItem).filter(ImageItem.id == img_id).first()
    assert db_img.metadata_status == "FAILED"
    db_meta = db.query(ImageMetadata).filter(ImageMetadata.image_id == img_id).first()
    # MUST NOT create fake template metadata!
    assert db_meta is None
    db.close()
