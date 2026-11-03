import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, asc, cast, Date
import imagehash
from app.models.image import ImageItem
from app.models.category import Category
from app.models.metadata import ImageMetadata
from app.models.batch import UploadBatch


class ImageRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, image_id: int) -> Optional[ImageItem]:
        return (
            self.db.query(ImageItem)
            .options(joinedload(ImageItem.category), joinedload(ImageItem.metadata_rel))
            .filter(ImageItem.id == image_id)
            .first()
        )

    def get_by_uuid(self, uuid_str: str) -> Optional[ImageItem]:
        return self.db.query(ImageItem).filter(ImageItem.uuid == uuid_str).first()

    def get_by_sha256(self, sha256_hash: str) -> Optional[ImageItem]:
        return self.db.query(ImageItem).filter(ImageItem.sha256 == sha256_hash).first()

    def find_duplicate_by_phash(self, target_phash_hex: str, max_distance: int = 5) -> Optional[Tuple[ImageItem, float]]:
        """Compare pHash against database using hamming distance"""
        try:
            target_hash = imagehash.hex_to_hash(target_phash_hex)
        except Exception:
            return None

        # Fetch candidates with valid phashes
        candidates = (
            self.db.query(ImageItem)
            .filter(ImageItem.phash != None, ImageItem.phash != "")
            .all()
        )
        best_match = None
        min_dist = float("inf")

        for item in candidates:
            try:
                candidate_hash = imagehash.hex_to_hash(item.phash)
                dist = target_hash - candidate_hash  # Hamming distance
                if dist <= max_distance and dist < min_dist:
                    min_dist = dist
                    best_match = item
            except Exception:
                continue

        if best_match:
            # Hash size is 64 bits. Similarity % = (1 - (dist / 64)) * 100
            similarity = max(0.0, (1.0 - (min_dist / 64.0)) * 100.0)
            return best_match, similarity

        return None

    def list_images(
        self,
        status: Optional[str] = None,
        category_id: Optional[int] = None,
        search: Optional[str] = None,
        quality_status: Optional[str] = None,
        is_duplicate: Optional[bool] = None,
        metadata_status: Optional[str] = None,
        drive_status: Optional[str] = None,
        batch_id: Optional[str] = None,
        page: int = 1,
        size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Tuple[List[ImageItem], int]:
        query = self.db.query(ImageItem).options(joinedload(ImageItem.category), joinedload(ImageItem.metadata_rel))

        if status:
            query = query.filter(ImageItem.status == status.upper())
        if category_id:
            query = query.filter(ImageItem.category_id == category_id)
        if quality_status:
            query = query.filter(ImageItem.quality_status == quality_status.upper())
        if is_duplicate is not None:
            query = query.filter(ImageItem.is_duplicate == is_duplicate)
        if metadata_status:
            query = query.filter(ImageItem.metadata_status == metadata_status.upper())
        if drive_status:
            query = query.filter(ImageItem.drive_status == drive_status.upper())
        if batch_id:
            query = query.filter(ImageItem.batch_id == batch_id)
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                (ImageItem.original_filename.ilike(search_filter)) |
                (ImageItem.filename.ilike(search_filter)) |
                (ImageItem.rejection_reason.ilike(search_filter)) |
                (ImageItem.review_reason.ilike(search_filter))
            )

        total = query.count()

        # Sorting
        sort_column = getattr(ImageItem, sort_by, ImageItem.created_at)
        if sort_order.lower() == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))

        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def count_by_status(self) -> Dict[str, int]:
        counts = {
            "total_images": self.db.query(func.count(ImageItem.id)).scalar() or 0,
            "approved": self.db.query(func.count(ImageItem.id)).filter(ImageItem.status == "APPROVED").scalar() or 0,
            "rejected": self.db.query(func.count(ImageItem.id)).filter(ImageItem.status == "REJECTED").scalar() or 0,
            "review_required": self.db.query(func.count(ImageItem.id)).filter(ImageItem.status == "REVIEW_REQUIRED").scalar() or 0,
            "duplicates": self.db.query(func.count(ImageItem.id)).filter(ImageItem.status == "DUPLICATE").scalar() or 0,
            "metadata_completed": self.db.query(func.count(ImageItem.id)).filter(ImageItem.metadata_status == "COMPLETED").scalar() or 0,
            "pending_metadata": self.db.query(func.count(ImageItem.id)).filter(ImageItem.status == "APPROVED", ImageItem.metadata_status != "COMPLETED").scalar() or 0,
            "drive_uploads": self.db.query(func.count(ImageItem.id)).filter(ImageItem.drive_status == "COMPLETED").scalar() or 0,
        }
        return counts

    def get_recent(self, limit: int = 10) -> List[ImageItem]:
        return (
            self.db.query(ImageItem)
            .options(joinedload(ImageItem.category))
            .order_by(desc(ImageItem.created_at))
            .limit(limit)
            .all()
        )

    def get_daily_volume(self, days: int = 7) -> List[Dict[str, Any]]:
        since_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        # Group by cast(created_at as Date)
        results = (
            self.db.query(
                func.date(ImageItem.created_at).label("day"),
                ImageItem.status,
                func.count(ImageItem.id)
            )
            .filter(ImageItem.created_at >= since_date)
            .group_by(
                func.date(ImageItem.created_at),
                ImageItem.status
            )
            .order_by("day")
            .all()
        )

        daily_dict = {}
        # Pre-fill all days
        for i in range(days):
            d_str = (since_date + datetime.timedelta(days=i + 1)).strftime("%Y-%m-%d")
            daily_dict[d_str] = {
                "date": d_str,
                "total": 0,
                "approved": 0,
                "rejected": 0,
                "review_required": 0,
                "duplicates": 0,
            }

        for day, status, count in results:
            d_str = day.strftime("%Y-%m-%d") if hasattr(day, "strftime") else str(day)
            if d_str not in daily_dict:
                daily_dict[d_str] = {
                    "date": d_str,
                    "total": 0,
                    "approved": 0,
                    "rejected": 0,
                    "review_required": 0,
                    "duplicates": 0,
                }
            daily_dict[d_str]["total"] += count
            if status == "APPROVED":
                daily_dict[d_str]["approved"] += count
            elif status == "REJECTED":
                daily_dict[d_str]["rejected"] += count
            elif status == "REVIEW_REQUIRED":
                daily_dict[d_str]["review_required"] += count
            elif status == "DUPLICATE":
                daily_dict[d_str]["duplicates"] += count

        return list(daily_dict.values())

    def get_category_distribution(self) -> List[Dict[str, Any]]:
        total = self.db.query(func.count(ImageItem.id)).scalar() or 0
        if total == 0:
            return []

        results = (
            self.db.query(
                ImageItem.category_id,
                Category.name.label("category_name"),
                func.count(ImageItem.id).label("count")
            )
            .outerjoin(Category, ImageItem.category_id == Category.id)
            .group_by(ImageItem.category_id, Category.name)
            .order_by(desc("count"))
            .all()
        )

        items = []
        for cat_id, cat_name, cnt in results:
            items.append({
                "category_id": cat_id,
                "category_name": cat_name if cat_name else "Uncategorized",
                "count": cnt,
                "percentage": round((cnt / total) * 100, 1)
            })
        return items

    def get_quality_stats(self) -> Dict[str, Any]:
        passed = self.db.query(func.count(ImageItem.id)).filter(ImageItem.quality_status == "PASSED").scalar() or 0
        failed = self.db.query(func.count(ImageItem.id)).filter(ImageItem.quality_status == "FAILED").scalar() or 0
        avg_blur = self.db.query(func.avg(ImageItem.blur_score)).filter(ImageItem.blur_score != None).scalar() or 0.0
        return {
            "passed": passed,
            "failed": failed,
            "average_blur_score": round(float(avg_blur), 2)
        }

    def get_performance_stats(self) -> Dict[str, Any]:
        avg_ms = self.db.query(func.avg(ImageItem.processing_duration_ms)).filter(ImageItem.processing_duration_ms != None).scalar() or 0.0
        min_ms = self.db.query(func.min(ImageItem.processing_duration_ms)).filter(ImageItem.processing_duration_ms != None).scalar() or 0.0
        max_ms = self.db.query(func.max(ImageItem.processing_duration_ms)).filter(ImageItem.processing_duration_ms != None).scalar() or 0.0
        return {
            "average_duration_ms": round(float(avg_ms), 1),
            "fastest_duration_ms": round(float(min_ms), 1),
            "slowest_duration_ms": round(float(max_ms), 1),
        }
