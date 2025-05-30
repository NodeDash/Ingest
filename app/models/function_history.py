from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class FunctionHistory(Base):
    __tablename__ = "function_history"

    id = Column(Integer, primary_key=True, index=True)
    function_id = Column(Integer, ForeignKey("functions.id"), nullable=False)
    flow_id = Column(
        Integer, ForeignKey("flows.id"), nullable=True
    )  # New field for tracking flow ID
    status = Column(String, nullable=False)  # "success", "error"
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    execution_time = Column(Integer, nullable=True)  # in milliseconds
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    function = relationship("Function", backref="history")
    flow = relationship("Flow", backref="function_history_entries")  # New relationship
