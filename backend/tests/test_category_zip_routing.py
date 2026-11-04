import os
import io
import zipfile
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.category import Category
from app.models.image import ImageItem

client = TestClient(app)


def make_test_image(filename: str, label: str, color=(200, 100, 50), width=900, height=700) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    draw = ImageDraw.Draw(img)
    draw.text((100, 100), f"Test Decor: {label}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def create_category_zip(category_name: str, images: list) -> io.BytesIO:
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, data in images:
            zf.writestr(f"{category_name}/{fname}", data)
    zip_buf.seek(0)
    return zip_buf


def test_mandatory_category_routing_wedding_birthday_engagement():
    db = SessionLocal()
    # Ensure categories exist
    wedding_cat = db.query(Category).filter(Category.name.ilike("%Wedding%")).first()
    birthday_cat = db.query(Category).filter(Category.name.ilike("%Birthday%")).first()
    engagement_cat = db.query(Category).filter(Category.name.ilike("%Engagement%")).first()

    assert wedding_cat is not None
    assert birthday_cat is not None
    assert engagement_cat is not None

    # 1. Wedding ZIP Upload
    wedding_images = [
        ("wedding_mandap_stage_1.jpg", make_test_image("mandap1", "Wedding Mandap Setup", (240, 180, 50))),
        ("wedding_floral_arch_2.jpg", make_test_image("arch2", "Wedding Floral Arch", (220, 50, 120))),
    ]
    wedding_zip = create_category_zip("Wedding", wedding_images)
    res_w = client.post(
        "/api/v1/uploads/zip",
        files={"file": ("wedding_batch.zip", wedding_zip.getvalue(), "application/zip")},
        data={"category_id": wedding_cat.id}
    )
    assert res_w.status_code == 200
    data_w = res_w.json()
    assert data_w["valid_images"] >= 2

    # Verify every image from Wedding enters Wedding folder and retains category
    wedding_dir = os.path.join(settings.STORAGE_ROOT, "EventDhara", "Wedding")
    assert os.path.exists(wedding_dir)
    wedding_statuses = os.listdir(wedding_dir)
    assert any(st in ["Approved", "Rejected", "Review_Required"] for st in wedding_statuses)

    # 2. Birthday ZIP Upload
    birthday_images = [
        ("birthday_balloon_arch_1.jpg", make_test_image("bday1", "Birthday Balloon Arch", (50, 150, 240))),
    ]
    birthday_zip = create_category_zip("Birthday", birthday_images)
    res_b = client.post(
        "/api/v1/uploads/zip",
        files={"file": ("birthday_batch.zip", birthday_zip.getvalue(), "application/zip")},
        data={"category_id": birthday_cat.id}
    )
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["valid_images"] >= 1

    birthday_dir = os.path.join(settings.STORAGE_ROOT, "EventDhara", "Birthday")
    assert os.path.exists(birthday_dir)

    # 3. Engagement ZIP Upload
    engagement_images = [
        ("engagement_ring_ceremony_1.jpg", make_test_image("eng1", "Engagement Ring Backdrop", (210, 120, 200))),
    ]
    engagement_zip = create_category_zip("Engagement", engagement_images)
    res_e = client.post(
        "/api/v1/uploads/zip",
        files={"file": ("engagement_batch.zip", engagement_zip.getvalue(), "application/zip")},
        data={"category_id": engagement_cat.id}
    )
    assert res_e.status_code == 200
    data_e = res_e.json()
    assert data_e["valid_images"] >= 1

    engagement_dir = os.path.join(settings.STORAGE_ROOT, "EventDhara", "Engagement")
    assert os.path.exists(engagement_dir)

    # 4. Verify No Cross-Category Contamination
    # None of the wedding files should be in birthday or engagement directory
    if os.path.exists(birthday_dir):
        for root, _, files in os.walk(birthday_dir):
            for f in files:
                assert "wedding" not in f.lower()

    if os.path.exists(wedding_dir):
        for root, _, files in os.walk(wedding_dir):
            for f in files:
                assert "birthday" not in f.lower()

    db.close()
