import os
import tempfile
import pytest
from PIL import Image
from app.services.processing_service import ProcessingService
from app.services.duplicate_service import DuplicateService
from app.core.database import SessionLocal


def test_sha256_and_phash_computation():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Create test solid image
        img = Image.new("RGB", (900, 700), color=(255, 120, 50))
        img.save(tmp_path)

        sha = DuplicateService.compute_sha256(tmp_path)
        assert len(sha) == 64

        phash = DuplicateService.compute_phash(tmp_path)
        assert len(phash) > 0
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_quality_and_blur_detection():
    db = SessionLocal()
    processor = ProcessingService(db)
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Create a sharp image
        img = Image.new("RGB", (1000, 800), color=(200, 200, 200))
        img.save(tmp_path)

        blur_score = processor.compute_blur_score(tmp_path)
        assert isinstance(blur_score, float)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        db.close()
