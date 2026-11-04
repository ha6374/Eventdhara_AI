import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class RejectionFeedback(Base):
    __tablename__ = "rejection_feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    image_path = Column(String(512), nullable=False)
    original_category = Column(String(100), nullable=True, index=True)
    predicted_category = Column(String(100), nullable=True)
    rejection_reason = Column(String(100), nullable=False, index=True)
    custom_feedback = Column(Text, nullable=True)
    ai_confidence_score = Column(Float, nullable=True)
    previous_status = Column(String(30), nullable=True)
    insights = Column(Text, nullable=True)  # Structured feedback insights from Gemini
    user_id = Column(String(100), default="operator", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    image = relationship("ImageItem", backref="feedbacks")

    def __repr__(self):
        return f"<RejectionFeedback id={self.id} image_id={self.image_id} reason='{self.rejection_reason}'>"


class CategoryFeedbackInsight(Base):
    __tablename__ = "category_feedback_insights"

    id = Column(Integer, primary_key=True, index=True)
    category_name = Column(String(100), unique=True, index=True, nullable=False)
    pattern_summary = Column(Text, nullable=False)
    rejection_count = Column(Integer, default=1, nullable=False)
    rules_to_enforce = Column(Text, nullable=True)  # JSON string of rules to enforce in prompt
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<CategoryFeedbackInsight category='{self.category_name}' count={self.rejection_count}>"
