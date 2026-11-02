import hashlib
import logging
from typing import Tuple, Optional
from PIL import Image
import imagehash
from sqlalchemy.orm import Session
from app.repositories.image_repo import ImageRepository
from app.models.image import ImageItem
from app.core.config import settings

logger = logging.getLogger("eventdhara.duplicate_service")


class DuplicateService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ImageRepository(db)

    @staticmethod
    def compute_sha256(file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def compute_phash(file_path: str) -> str:
        try:
            with Image.open(file_path) as img:
                h = imagehash.phash(img)
                return str(h)
        except Exception as e:
            logger.error("Failed to calculate pHash for %s: %s", file_path, e)
            return ""

    def check_global_duplicate(
        self,
        sha256_hash: str,
        phash_str: str,
        exclude_id: Optional[int] = None
    ) -> Tuple[bool, Optional[ImageItem], float, Optional[str]]:
        """
        Performs global duplicate check against all stored images:
        1. Exact SHA256 collision
        2. Perceptual pHash hamming distance within threshold
        Returns (is_dup, original_item, similarity_pct, dup_type)
        """
        # 1. SHA256 exact match check
        query = self.db.query(ImageItem).filter(ImageItem.sha256 == sha256_hash)
        if exclude_id:
            query = query.filter(ImageItem.id != exclude_id)
        exact_match = query.first()

        if exact_match:
            logger.info("Found exact SHA256 duplicate with Image ID %s", exact_match.id)
            return True, exact_match, 100.0, "SHA256_EXACT"

        # 2. Perceptual pHash visual match check
        if phash_str:
            match = self.repo.find_duplicate_by_phash(phash_str, max_distance=settings.PHASH_THRESHOLD)
            if match:
                candidate, similarity = match
                if not exclude_id or candidate.id != exclude_id:
                    logger.info("Found visual pHash duplicate (%s%% similarity) with Image ID %s", similarity, candidate.id)
                    return True, candidate, similarity, "PHASH_VISUAL"

        return False, None, 0.0, None
