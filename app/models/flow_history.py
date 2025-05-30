from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class FlowHistory(Base):
    __tablename__ = "flow_history"

    id = Column(Integer, primary_key=True, index=True)
    flow_id = Column(Integer, ForeignKey("flows.id"), nullable=False)
    status = Column(String, nullable=False)  # "success", "error", "partial"
    trigger_source = Column(
        String, nullable=True
    )  # "device_uplink", "scheduled", "manual", etc.
    source_id = Column(
        Integer, nullable=True
    )  # ID of the triggering device/label if applicable
    execution_path = Column(
        JSON, nullable=True
    )  # Stores the path of nodes that were executed
    error_details = Column(Text, nullable=True)  # Details about any errors encountered
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    execution_time = Column(Integer, nullable=True)  # in milliseconds
    timestamp = Column(
        DateTime, default=datetime.utcnow
    )  # Timestamp of the history entry
    input_data = Column(JSON, nullable=True)  # Input data to the flow
    output_data = Column(JSON, nullable=True)  # Output data from the flow

    # Relationship
    flow = relationship("Flow", backref="history")
