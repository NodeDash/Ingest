"""
Authentication and security utilities.
Handles API key validation for ingest endpoints.
"""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

# Define API key header dependency
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """
    Verify the API key from the X-API-Key header.
    This is a simple security check for the ingest service.
    
    More sophisticated API key validation is done in the endpoint
    function based on provider configurations.

    Args:
        api_key: API key from request header

    Returns:
        The verified API key

    Raises:
        HTTPException: If API key is invalid
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
        )
    
    # Basic validation to prevent obvious errors
    if len(api_key) < 8:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
        )
    
    # Actual validation happens in the endpoint itself
    # based on provider configuration
    return api_key
