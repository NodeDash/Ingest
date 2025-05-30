from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class DeviceHistory(Base):
    __tablename__ = "device_history"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    flow_id = Column(
        Integer, ForeignKey("flows.id"), nullable=True
    )  # Field for tracking flow ID
    event = Column(String, nullable=False)
    data = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # We still need to define the relationship here as a string reference
    device = relationship("Device", back_populates="histories")

    # Relationship to Flow is fine because it's not circular
    flow = relationship("Flow", backref="device_history_entries")
