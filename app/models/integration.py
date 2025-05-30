from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.db.database import Base
from app.models.enums import OwnerType, IntegrationStatus, IntegrationType


class Integration(Base):
    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    type = Column(String, nullable=False)
    config = Column(JSON, nullable=False)
    status = Column(String, default=IntegrationStatus.INACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner_type = Column(String, default=OwnerType.USER)
    owner = relationship("User", foreign_keys=[owner_id])
