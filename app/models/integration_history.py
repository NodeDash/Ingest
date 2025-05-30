from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class IntegrationHistory(Base):
    __tablename__ = "integration_history"

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("integrations.id"), nullable=False)
    flow_id = Column(
        Integer, ForeignKey("flows.id"), nullable=True
    )  # New field for tracking flow ID
    status = Column(String, nullable=False)  # "success", "error"
    input_data = Column(JSON, nullable=True)
    response_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    execution_time = Column(Integer, nullable=True)  # in milliseconds
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    integration = relationship("Integration", backref="history")
    flow = relationship(
        "Flow", backref="integration_history_entries"
    )  # New relationship
