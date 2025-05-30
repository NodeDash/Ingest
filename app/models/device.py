from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Table,
    Enum,
    Boolean,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import List
from app.db.database import Base
import enum
from app.models.enums import OwnerType, DeviceStatus, Region

# Association table for many-to-many relationship between devices and labels
device_label = Table(
    "device_label",
    Base.metadata,
    Column("device_id", Integer, ForeignKey("devices.id"), primary_key=True),
    Column("label_id", Integer, ForeignKey("labels.id"), primary_key=True),
)


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    dev_eui = Column(String(16), nullable=False, unique=True, index=True)
    app_eui = Column(String(16), nullable=False)
    app_key = Column(String(32), nullable=False)
    status = Column(String, default=DeviceStatus.NEVER_SEEN)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Expected transmit time in minutes (from 1 minute to 24 hours)
    expected_transmit_time = Column(Integer, nullable=True)
    # Add owner fields
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner_type = Column(String, default=OwnerType.USER)
    # Added new fields
    region = Column(Enum(Region), nullable=True)
    is_class_c = Column(Boolean, default=False)

    # Relationships
    labels = relationship("Label", secondary=device_label, back_populates="devices")
    owner = relationship("User", foreign_keys=[owner_id])


# The relationship with DeviceHistory needs to be defined after both classes
# Import DeviceHistory here to avoid circular imports
from app.models.device_history import DeviceHistory

# Now attach the relationship to the Device class
Device.histories = relationship(
    "DeviceHistory", back_populates="device", cascade="all, delete-orphan"
)
