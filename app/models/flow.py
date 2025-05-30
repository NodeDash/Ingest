from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base
from app.models.enums import OwnerType


class Flow(Base):
    __tablename__ = "flows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(String, nullable=True)
    nodes = Column(JSON, nullable=True)
    edges = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Add owner fields
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner_type = Column(String, default=OwnerType.USER)

    # Flow layout is stored separately
    layout = Column(JSON, nullable=True)

    # Add relationship to owner
    owner = relationship("User", foreign_keys=[owner_id])
