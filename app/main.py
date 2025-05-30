"""
Main application entry point.
Initializes FastAPI app and configures middleware, routes, and startup/shutdown events.
"""

import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.api import api_router
from app.core.config import settings
from app.redis.client import RedisClient

# Import all models to ensure they're registered with SQLAlchemy
from app.models import *  # noqa

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log request details"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Process the request
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time
        process_time_ms = int(process_time * 1000)

        # Log request details
        logger.info(
            f"{request.method} {request.url.path} {response.status_code} {process_time_ms}ms"
        )

        # Add custom header with processing time
        response.headers["X-Process-Time"] = str(process_time_ms)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI app.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Initializing Redis connection")
    redis_client = RedisClient.get_instance()

    # Check if Redis connection is successful
    if redis_client.redis:
        logger.info("Redis connection successful")
    else:
        logger.warning("Redis connection failed, continuing without Redis")

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Application shutting down")


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Add API router
app.include_router(api_router, prefix=settings.API_V1_STR)


# Root endpoint for quick status check
@app.get("/", tags=["status"])
def root():
    """
    Root endpoint for quick status check.
    """
    return {
        "service": "device-manager-ingest",
        "status": "running",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    """
    Run the application locally using uvicorn.
    This is used for development, not production.
    """
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
