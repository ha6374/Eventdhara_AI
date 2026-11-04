import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class ImageMetadata(Base):
    __tablename__ = "image_metadata"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    name = Column(String(255), nullable=False)
    short_description = Column(Text, nullable=False)
    long_description = Column(Text, nullable=False)
    inclusion = Column(Text, nullable=True)  # JSON serialized list of inclusions
    faq = Column(Text, nullable=True)        # JSON serialized list of FAQs
    note = Column(Text, nullable=True)
    keywords = Column(Text, nullable=True)   # JSON serialized list or comma-separated
    tags = Column(Text, nullable=True)       # JSON serialized list or comma-separated
    custom_fields = Column(Text, nullable=True)  # JSON serialized dictionary of dynamic fields

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    image = relationship("ImageItem", back_populates="metadata_rel")

    def __repr__(self):
        return f"<ImageMetadata id={self.id} image_id={self.image_id} name='{self.name}'>"
