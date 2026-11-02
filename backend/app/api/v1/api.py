from fastapi import APIRouter
from app.api.v1.endpoints import (
    dashboard,
    categories,
    uploads,
    processing,
    images,
    duplicates,
    metadata,
    drive,
    reports,
    settings as settings_ep
)

api_router = APIRouter()

api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(categories.router, prefix="/categories", tags=["Category Management"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["Upload Center"])
api_router.include_router(processing.router, prefix="/processing", tags=["Processing Engine"])
api_router.include_router(images.router, prefix="/images", tags=["Image Operations & Galleries"])
api_router.include_router(duplicates.router, prefix="/duplicates", tags=["Duplicate Center"])
api_router.include_router(metadata.router, prefix="/metadata", tags=["Metadata Studio"])
api_router.include_router(drive.router, prefix="/google-drive", tags=["Google Drive Cloud"])
api_router.include_router(reports.router, prefix="/reports", tags=["Analytics & Reports"])
api_router.include_router(settings_ep.router, prefix="/settings", tags=["System Settings"])
