"""
API router configuration.
Defines the main API routes and includes all endpoint routers.
"""

from fastapi import APIRouter

from app.api.endpoints import ingest, health

# Create main API router
api_router = APIRouter()

# Include all endpoint routers with their prefixes
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
