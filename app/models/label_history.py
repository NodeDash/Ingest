from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class LabelHistory(Base):
    __tablename__ = "label_history"

    id = Column(Integer, primary_key=True, index=True)
    label_id = Column(Integer, ForeignKey("labels.id"), nullable=False)
    flow_id = Column(Integer, ForeignKey("flows.id"), nullable=True)
    event = Column(String, nullable=False)
    data = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String, nullable=True)  # Add status column to track label state

    # Relationships
    label = relationship("Label", backref="histories")
    flow = relationship("Flow", backref="label_history_entries")
