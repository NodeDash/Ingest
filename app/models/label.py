from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base
from app.models.device import device_label
from app.models.enums import OwnerType


class Label(Base):
    __tablename__ = "labels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Add owner fields
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner_type = Column(String, default=OwnerType.USER)

    # Relationships
    devices = relationship("Device", secondary=device_label, back_populates="labels")
    owner = relationship("User", foreign_keys=[owner_id])
