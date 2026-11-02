import datetime
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class ImageItem(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    storage_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False)  # in bytes
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    format = Column(String(20), nullable=False)

    # Hashes for duplicate detection
    sha256 = Column(String(64), index=True, nullable=False)
    phash = Column(String(64), index=True, nullable=False)

    # Quality check metrics
    blur_score = Column(Float, nullable=True)  # Laplacian variance
    quality_status = Column(String(20), default="PENDING", nullable=False)  # PASSED, FAILED

    # Pipeline Status: PENDING, APPROVED, REJECTED, REVIEW_REQUIRED, DUPLICATE
    status = Column(String(30), default="PENDING", index=True, nullable=False)
    rejection_reason = Column(Text, nullable=True)
    review_reason = Column(Text, nullable=True)

    # Duplicate relations
    is_duplicate = Column(Boolean, default=False, nullable=False)
    duplicate_of_id = Column(Integer, ForeignKey("images.id", ondelete="SET NULL"), nullable=True)
    duplicate_similarity = Column(Float, nullable=True)
    duplicate_type = Column(String(30), nullable=True)  # SHA256_EXACT, PHASH_VISUAL

    # AI Classification (Gemini)
    ai_classification = Column(Text, nullable=True)  # Stored JSON string
    ai_confidence = Column(Float, nullable=True)

    # Category relation
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)

    # Metadata & Cloud Upload Statuses
    metadata_status = Column(String(30), default="PENDING", nullable=False)  # PENDING, PROCESSING, COMPLETED, FAILED
    drive_status = Column(String(30), default="PENDING", nullable=False)     # PENDING, UPLOADING, COMPLETED, FAILED
    drive_file_id = Column(String(255), nullable=True)
    drive_url = Column(Text, nullable=True)
    drive_uploaded_at = Column(DateTime, nullable=True)

    # Batch and processing stats
    batch_id = Column(String(36), ForeignKey("upload_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    processing_duration_ms = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationships
    category = relationship("Category", back_populates="images")
    batch = relationship("UploadBatch", back_populates="images")
    metadata_rel = relationship("ImageMetadata", back_populates="image", uselist=False, cascade="all, delete-orphan")
    duplicate_of = relationship("ImageItem", remote_side=[id], backref="duplicates")

    def __repr__(self):
        return f"<ImageItem id={self.id} filename='{self.filename}' status='{self.status}'>"
