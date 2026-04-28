import time
import json
import asyncio
from typing import Any, Optional, Callable, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.models import CacheEntry
import logging

logger = logging.getLogger(__name__)

class PersistentSWRCache:
    """
    A persistent cache with Stale-While-Revalidate (SWR) logic.
    - Sub-100ms response if hit.
    - Background refresh if stale.
    - DB-backed persistence.
    """
    def __init__(self, name: str, db_session_factory: Callable[[], Session], ttl_seconds: int = 3600, stale_seconds: int = 86400):
        self.name = name
        self.db_session_factory = db_session_factory
        self.ttl_seconds = ttl_seconds
        self.stale_seconds = stale_seconds
        self._memory_cache: Dict[str, Any] = {}

    def _get_db_session(self) -> Session:
        return self.db_session_factory()

    async def get(self, key: str, revalidate_func: Optional[Callable] = None, *args, **kwargs) -> Optional[Any]:
        full_key = f"{self.name}:{key}"
        now = datetime.utcnow()

        # 1. Check Memory Cache (L1)
        if full_key in self._memory_cache:
            val, expiry = self._memory_cache[full_key]
            if now < expiry:
                return val

        # 2. Check Database (L2)
        db = self._get_db_session()
        try:
            entry = db.query(CacheEntry).filter(CacheEntry.key == full_key).first()
            if not entry:
                return None

            # Check if value is still valid
            is_stale = now > (entry.created_at + timedelta(seconds=self.ttl_seconds))
            is_expired = now > (entry.created_at + timedelta(seconds=self.stale_seconds))

            if is_expired:
                db.delete(entry)
                db.commit()
                return None

            # Update memory cache
            self._memory_cache[full_key] = (entry.value, entry.created_at + timedelta(seconds=self.ttl_seconds))

            if is_stale and revalidate_func:
                # Trigger background revalidation
                asyncio.create_task(self._revalidate(full_key, revalidate_func, *args, **kwargs))
            
            return entry.value
        except Exception as e:
            logger.error(f"Cache get error for {full_key}: {e}")
            return None
        finally:
            db.close()

    async def set(self, key: str, value: Any):
        full_key = f"{self.name}:{key}"
        now = datetime.utcnow()
        
        # Update Memory
        self._memory_cache[full_key] = (value, now + timedelta(seconds=self.ttl_seconds))
        
        # Update DB
        db = self._get_db_session()
        try:
            entry = db.query(CacheEntry).filter(CacheEntry.key == full_key).first()
            if entry:
                entry.value = value
                entry.created_at = now
            else:
                entry = CacheEntry(key=full_key, value=value, created_at=now)
                db.add(entry)
            db.commit()
        except Exception as e:
            logger.error(f"Cache set error for {full_key}: {e}")
        finally:
            db.close()

    async def _revalidate(self, full_key: str, func: Callable, *args, **kwargs):
        """Internal helper to refresh data in background."""
        try:
            logger.info(f"Revalidating cache for {full_key}...")
            new_value = await func(*args, **kwargs)
            if new_value:
                # Stip the prefix for the .set call as it adds it again
                base_key = full_key.split(":", 1)[1]
                await self.set(base_key, new_value)
        except Exception as e:
            logger.error(f"Background revalidation failed for {full_key}: {e}")

    def invalidate(self, key: str):
        full_key = f"{self.name}:{key}"
        if full_key in self._memory_cache:
            del self._memory_cache[full_key]
        
        db = self._get_db_session()
        try:
            db.query(CacheEntry).filter(CacheEntry.key == full_key).delete()
            db.commit()
        finally:
            db.close()

# Helper for global session access (needed for worker/background tasks)
from app.core.database import SessionLocal

# Global cache instances
course_cache = PersistentSWRCache("syllabus", lambda: SessionLocal(), ttl_seconds=86400, stale_seconds=604800) # 1 day TTL, 7 day stale
topic_cache = PersistentSWRCache("topic", lambda: SessionLocal(), ttl_seconds=172800, stale_seconds=1209600)   # 2 day TTL, 14 day stale
media_cache = PersistentSWRCache("media", lambda: SessionLocal(), ttl_seconds=259200, stale_seconds=2592000)   # 3 day TTL, 30 day stale

# Aliases for backward compatibility
knowledge_map_cache = course_cache
podcast_cache = media_cache
