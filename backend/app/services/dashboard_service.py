import logging
from sqlalchemy.orm import Session
from app.repositories.image_repo import ImageRepository
from app.repositories.category_repo import CategoryRepository
from app.schemas.dashboard import (
    DashboardOverviewResponse,
    DashboardStats,
    DailyProcessingVolume,
    CategoryDistributionItem,
    QualityDistribution,
    ProcessingPerformance,
    RecentActivityItem
)

logger = logging.getLogger("eventdhara.dashboard_service")


class DashboardService:
    def __init__(self, db: Session):
        self.db = db
        self.image_repo = ImageRepository(db)
        self.category_repo = CategoryRepository(db)

    def get_overview(self) -> DashboardOverviewResponse:
        # All live metrics fetched from PostgreSQL
        counts = self.image_repo.count_by_status()
        stats = DashboardStats(**counts)

        # Daily volumes
        daily_raw = self.image_repo.get_daily_volume(days=7)
        daily_volume = [DailyProcessingVolume(**item) for item in daily_raw]

        # Category distribution
        cat_dist_raw = self.image_repo.get_category_distribution()
        cat_distribution = [CategoryDistributionItem(**item) for item in cat_dist_raw]

        # Quality distribution
        q_stats = self.image_repo.get_quality_stats()
        quality_dist = QualityDistribution(**q_stats)

        # Processing performance
        perf = self.image_repo.get_performance_stats()
        performance = ProcessingPerformance(**perf)

        # Recent activity
        recent_images = self.image_repo.get_recent(limit=8)
        recent_activity = []
        for img in recent_images:
            cat_name = img.category.name if img.category else "Unassigned"
            recent_activity.append(RecentActivityItem(
                id=img.id,
                filename=img.original_filename,
                category=cat_name,
                status=img.status,
                created_at=img.created_at,
                processing_duration_ms=img.processing_duration_ms,
                quality_status=img.quality_status
            ))

        return DashboardOverviewResponse(
            stats=stats,
            daily_volume=daily_volume,
            category_distribution=cat_distribution,
            quality_distribution=quality_dist,
            processing_performance=performance,
            recent_activity=recent_activity
        )
