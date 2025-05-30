"""
Health check endpoints for service status monitoring.
"""

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import get_db
from app.redis.client import RedisClient

router = APIRouter()


@router.get("/", summary="Health check endpoint")
def health_check() -> Dict[str, Any]:
    """
    Basic health check that returns service status.
    Used by Kubernetes to check if the service is alive.
    """
    return {
        "status": "healthy",
        "service": "device-manager-ingest",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/readiness", summary="Readiness check endpoint")
def readiness_check(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Readiness check that verifies database connection.
    Used by Kubernetes to check if the service is ready to receive requests.
    """
    # Check DB connection
    db_status = "ok"
    db_error = None
    try:
        # Simple query to verify database connection
        db.execute(text("SELECT 1")).fetchall()
    except Exception as e:
        db_status = "error"
        db_error = str(e)

    # Check Redis connection
    redis_status = "ok"
    redis_error = None
    try:
        redis_client = RedisClient.get_instance()
        if not redis_client.redis or not redis_client.redis.ping():
            redis_status = "error"
            redis_error = "Redis connection failed"
    except Exception as e:
        redis_status = "error"
        redis_error = str(e)

    # Overall status
    overall_status = (
        "ready" if db_status == "ok" and redis_status == "ok" else "not_ready"
    )

    return {
        "status": overall_status,
        "service": "device-manager-ingest",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": {
                "status": db_status,
                "error": db_error,
            },
            "redis": {
                "status": redis_status,
                "error": redis_error,
            },
        },
    }
