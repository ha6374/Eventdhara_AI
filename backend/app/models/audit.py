import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    image_id = Column(Integer, nullable=True, index=True)
    details = Column(Text, nullable=False)
    performed_by = Column(String(100), default="System Operator", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AuditLog id={self.id} action='{self.action}' image_id={self.image_id}>"
