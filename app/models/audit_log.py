from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_email = Column(String(255), nullable=False, default="")
    action = Column(String(50), nullable=False, index=True)
    file_id = Column(Integer, ForeignKey("excel_files.id", ondelete="SET NULL"), nullable=True)
    file_name = Column(String(255), nullable=False, default="")
    ip_address = Column(String(45), nullable=False, default="")
    user_agent = Column(String(500), nullable=False, default="")
    metadata_ = Column("metadata", Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
