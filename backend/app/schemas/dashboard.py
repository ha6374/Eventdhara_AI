import datetime
from typing import List, Optional
from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_images: int = 0
    approved: int = 0
    rejected: int = 0
    review_required: int = 0
    duplicates: int = 0
    metadata_completed: int = 0
    pending_metadata: int = 0
    drive_uploads: int = 0


class DailyProcessingVolume(BaseModel):
    date: str
    total: int
    approved: int
    rejected: int
    review_required: int
    duplicates: int


class CategoryDistributionItem(BaseModel):
    category_id: Optional[int] = None
    category_name: str
    count: int
    percentage: float


class QualityDistribution(BaseModel):
    passed: int = 0
    failed: int = 0
    average_blur_score: float = 0.0


class ProcessingPerformance(BaseModel):
    average_duration_ms: float = 0.0
    fastest_duration_ms: float = 0.0
    slowest_duration_ms: float = 0.0


class RecentActivityItem(BaseModel):
    id: int
    filename: str
    category: str
    status: str
    created_at: datetime.datetime
    processing_duration_ms: Optional[float] = None
    quality_status: str


class DashboardOverviewResponse(BaseModel):
    stats: DashboardStats
    daily_volume: List[DailyProcessingVolume]
    category_distribution: List[CategoryDistributionItem]
    quality_distribution: QualityDistribution
    processing_performance: ProcessingPerformance
    recent_activity: List[RecentActivityItem]
