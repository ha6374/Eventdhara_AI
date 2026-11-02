import os
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models.image import ImageItem
from app.services.export_service import ExportService
from app.schemas.reports import ReportSummary

router = APIRouter()


@router.get("/summary", response_model=ReportSummary)
def get_report_summary(db: Session = Depends(get_db)):
    """Fetch breakdown summary for reports."""
    total = db.query(ImageItem).count()
    approved = db.query(ImageItem).filter(ImageItem.status == "APPROVED").count()
    rejected = db.query(ImageItem).filter(ImageItem.status == "REJECTED").count()
    review = db.query(ImageItem).filter(ImageItem.status == "REVIEW_REQUIRED").count()
    dups = db.query(ImageItem).filter(ImageItem.status == "DUPLICATE").count()

    # Rejection breakdown
    rejection_query = (
        db.query(ImageItem.rejection_reason, func.count(ImageItem.id))
        .filter(ImageItem.status == "REJECTED", ImageItem.rejection_reason != None)
        .group_by(ImageItem.rejection_reason)
        .limit(10)
        .all()
    )
    rejection_map = {reason or "Unspecified": count for reason, count in rejection_query}

    # Category breakdown
    cat_query = (
        db.query(ImageItem.category_id, func.count(ImageItem.id))
        .group_by(ImageItem.category_id)
        .all()
    )
    cat_map = {str(cat_id or "Unassigned"): count for cat_id, count in cat_query}

    return ReportSummary(
        period="All-Time Live Data",
        total_processed=total,
        total_approved=approved,
        total_rejected=rejected,
        total_review=review,
        total_duplicates=dups,
        rejection_breakdown=rejection_map,
        category_breakdown=cat_map
    )


@router.get("/export")
def export_dataset(
    status: Optional[str] = None,
    category_id: Optional[int] = None,
    format: str = Query("csv", pattern="^(csv|excel|xlsx)$"),
    db: Session = Depends(get_db)
):
    """Generate and download Excel or CSV report."""
    service = ExportService(db)
    file_path = service.export_images_data(
        status=status,
        category_id=category_id,
        export_format=format
    )

    if not os.path.exists(file_path):
        raise HTTPException(status_code=500, detail="Failed to generate export file")

    filename = os.path.basename(file_path)
    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if "xlsx" in filename
        else "text/csv"
    )

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )
