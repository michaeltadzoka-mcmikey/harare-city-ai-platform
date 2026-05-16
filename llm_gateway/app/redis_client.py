"""
Redis Client for Harare City Council LLM Gateway v5.6.2
Singleton Redis client with connection pooling and generic cache helpers.
"""

import logging
import redis
from typing import Optional

logger = logging.getLogger(__name__)

class RedisClient:
    """
    Singleton Redis client with automatic reconnection.
    """

    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._initialize_client()

    def _initialize_client(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        max_retries: int = 3
    ):
        """Initialize Redis client with connection pooling."""
        try:
            pool = redis.ConnectionPool(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                max_connections=10,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )

            self._client = redis.Redis(connection_pool=pool)

            # Test connection
            self._client.ping()

            logger.info(f"✓ Redis connected: {host}:{port}/db{db}")

        except redis.ConnectionError as e:
            logger.error(f"❌ Redis connection failed: {e}")
            logger.warning("Falling back to in-memory storage")
            self._client = None
        except Exception as e:
            logger.error(f"Redis initialization error: {e}")
            self._client = None

    def get_client(self) -> Optional[redis.Redis]:
        """Get Redis client instance."""
        if self._client:
            try:
                self._client.ping()
                return self._client
            except:
                logger.warning("Redis connection lost, attempting reconnect...")
                self._initialize_client()
                return self._client
        return None

    def is_available(self) -> bool:
        """Check if Redis is available."""
        client = self.get_client()
        if client:
            try:
                client.ping()
                return True
            except:
                return False
        return False

    def cache_get(self, key: str) -> Optional[str]:
        """Get value from cache if Redis available."""
        client = self.get_client()
        if client:
            try:
                return client.get(key)
            except:
                pass
        return None

    def cache_set(self, key: str, value: str, ttl: int):
        """Set value in cache if Redis available."""
        client = self.get_client()
        if client:
            try:
                client.setex(key, ttl, value)
            except:
                pass

# Global instance
redis_client_instance = RedisClient()

def get_redis_client() -> Optional[redis.Redis]:
    """Get global Redis client."""
    return redis_client_instance.get_client()