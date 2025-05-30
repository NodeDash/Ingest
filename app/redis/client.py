import redis
import json
import logging
from typing import Optional, Dict, Any, Union

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    _instance = None

    @classmethod
    def get_instance(cls) -> "RedisClient":
        """Get singleton instance of RedisClient"""
        if cls._instance is None:
            cls._instance = RedisClient()
        return cls._instance

    def __init__(self):
        """Initialize Redis connection"""
        try:
            # Configure Redis client
            self.redis = redis.Redis(
                host=settings.REDIS_HOST,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
            )
            logger.info(f"Connected to Redis at {settings.REDIS_HOST}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self.redis = None

    def set_device_online(self, device_id: int, ttl_seconds: int = 300) -> bool:
        """Set a device as online with an expiry time"""
        if not self.redis:
            logger.error("Redis client not available")
            return False

        try:
            key = f"device:status:{device_id}"
            self.redis.set(key, "online", ex=ttl_seconds)
            return True
        except Exception as e:
            logger.error(f"Failed to set device online status: {str(e)}")
            return False
