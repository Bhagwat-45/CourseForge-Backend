import os
import redis
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class RedisClient:
    """
    Singleton Redis Client for distributed state management.
    Handles circuit breakers, rate limiting, and caching.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            try:
                cls._instance.client = redis.from_url(
                    redis_url, 
                    decode_responses=True,
                    socket_connect_timeout=2, # Fast fail
                    socket_timeout=2,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                # Deferred ping: check connectivity on first real request instead of blocking startup
                # cls._instance.client.ping()
                logger.info(f"Redis client initialized for {redis_url} (Lazy connect)")
            except Exception as e:
                logger.critical(f"CRITICAL: Redis is OFFLINE at {redis_url}. Distributed Circuit Breaker and Caching are suspended. System is in 'Safe-Mode' (local state only). (Error: {e})")
                cls._instance.client = None
        return cls._instance

    def get_client(self):
        return self.client

    def is_ready(self) -> bool:
        """Heatlh check for Redis."""
        if not self.client: return False
        try:
            return self.client.ping()
        except:
            return False

# Global instance
redis_manager = RedisClient()
redis_client = redis_manager.get_client()
