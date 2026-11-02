import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id = Column(String(36), primary_key=True)  # UUID
    original_name = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=True)
    total_files = Column(Integer, default=0, nullable=False)
    valid_files = Column(Integer, default=0, nullable=False)
    invalid_files = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default="PENDING", nullable=False)  # PENDING, EXTRACTING, PROCESSING, COMPLETED, FAILED
    error_message = Column(Text, nullable=True)
    target_category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    images = relationship("ImageItem", back_populates="batch")
    target_category = relationship("Category")
