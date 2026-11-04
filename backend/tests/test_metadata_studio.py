import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.image import ImageItem

client = TestClient(app)


def test_metadata_generation_editing_and_regeneration():
    # 1. Upload test image (>50KB with unique entropy)
    import numpy as np
    import uuid, time
    seed = (int(time.time() * 1000) + 789) % (2**31 - 1)
    rng = np.random.RandomState(seed)
    meta_arr = rng.randint(60, 210, (750, 950, 3), dtype=np.uint8)
    img = Image.fromarray(meta_arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)

    unique_fn = f"meta_decor_{uuid.uuid4().hex[:8]}.jpg"
    up_res = client.post(
        "/api/v1/uploads/images",
        files={"files": (unique_fn, buf.getvalue(), "image/jpeg")}
    )
    assert up_res.status_code == 200
    img_id = up_res.json()["processed_items"][0]["id"]

    # 2. Approve the image so metadata can be generated
    app_res = client.patch(f"/api/v1/images/{img_id}/status", json={"status": "APPROVED"})
    assert app_res.status_code == 200

    # 3. Generate AI Metadata
    gen_res = client.post(f"/api/v1/metadata/generate/{img_id}")
    assert gen_res.status_code == 200
    meta = gen_res.json()

    # Verify all 9 fields exist and are populated
    assert "name" in meta and len(meta["name"]) > 0
    assert "short_description" in meta and len(meta["short_description"]) > 0
    assert "long_description" in meta and len(meta["long_description"]) > 0
    assert "inclusion" in meta and isinstance(meta["inclusion"], list)
    assert "faq" in meta and isinstance(meta["faq"], list)
    assert "note" in meta
    assert "keywords" in meta and isinstance(meta["keywords"], list)
    assert "tags" in meta and isinstance(meta["tags"], list)
    assert "photo" in meta

    meta_id = meta["id"]

    # 4. Edit metadata (including custom fields)
    update_res = client.put(
        f"/api/v1/metadata/{meta_id}",
        json={
            "name": "Updated Custom Haldi Backdrop",
            "short_description": "Custom updated description for testing",
            "custom_fields": {"Color Theme": "Yellow & Marigold", "Setup Time": "3 Hours"}
        }
    )
    assert update_res.status_code == 200
    updated_meta = update_res.json()
    assert updated_meta["name"] == "Updated Custom Haldi Backdrop"
    assert updated_meta["custom_fields"]["Color Theme"] == "Yellow & Marigold"

    # 5. Force regenerate metadata
    regen_res = client.post(f"/api/v1/metadata/regenerate/{img_id}")
    assert regen_res.status_code == 200
    regen_meta = regen_res.json()
    assert regen_meta["id"] == meta_id
    assert len(regen_meta["name"]) > 0

    # 6. Verify GET all metadata includes this record
    all_res = client.get("/api/v1/metadata/all")
    assert all_res.status_code == 200
    all_ids = [m["id"] for m in all_res.json()]
    assert meta_id in all_ids
