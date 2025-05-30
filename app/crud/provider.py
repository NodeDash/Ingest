"""
CRUD operations for provider management.
Handles operations for device providers like ChirpStack.
"""

from typing import Optional, List, Union

from sqlalchemy.orm import Session

from app.models.provider import Provider, ProviderType
from app.models.enums import OwnerType


def get_provider_by_owner(
    db: Session,
    owner_id: int,
    owner_type: Union[str, OwnerType],
    provider_type: Union[str, ProviderType],
) -> Optional[Provider]:
    """
    Get a provider by owner ID, owner type, and provider type.

    Args:
        db: Database session
        owner_id: Owner ID
        owner_type: Owner type (USER or TEAM)
        provider_type: Provider type (e.g., 'chirpstack')

    Returns:
        Provider object or None
    """
    # Convert string types to enums if needed
    if isinstance(owner_type, str):
        owner_type = OwnerType(owner_type)

    if isinstance(provider_type, str):
        provider_type = ProviderType(provider_type)

    return (
        db.query(Provider)
        .filter(
            Provider.owner_id == owner_id,
            Provider.owner_type == owner_type,
            Provider.provider_type == provider_type,
            Provider.is_active == True,
        )
        .first()
    )


def get_providers(
    db: Session,
    provider_type: Optional[Union[str, ProviderType]] = None,
    is_active: Optional[bool] = None,
) -> List[Provider]:
    """
    Get a list of providers, optionally filtered by type and active status.

    Args:
        db: Database session
        provider_type: Optional provider type filter
        is_active: Optional active status filter

    Returns:
        List of provider objects
    """
    query = db.query(Provider).filter(Provider.is_deleted == False)

    if provider_type:
        if isinstance(provider_type, str):
            provider_type = ProviderType(provider_type)
        query = query.filter(Provider.type == provider_type)

    if is_active is not None:
        query = query.filter(Provider.is_active == is_active)

    return query.all()
