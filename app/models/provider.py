from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Enum,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.enums import OwnerType, ProviderType


class Provider(Base):
    """
    Provider model for various types of services that can be used in the application.
    Each provider has a type (e.g., email, sms) and configuration settings.
    """

    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    provider_type = Column(Enum(ProviderType, name="provider_type"), nullable=False)
    config = Column(JSON, nullable=True)  # JSON field for provider-specific config
    is_active = Column(Boolean, default=True)

    # Ownership info - can be owned by a user or a team
    owner_id = Column(Integer, nullable=False)
    owner_type = Column(Enum(OwnerType, name="ownertype"), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
