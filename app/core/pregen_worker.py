import asyncio
import logging
from app.core.cache import topic_cache, course_cache
from app.agents.topic_agent import generate_topic_content
from app.agents.curriculum_agent import generate_course_syllabus
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# Topic names that are likely to be requested by new users
# NOTE: Keep this list SHORT to preserve free-tier API quota (20 req/day).
# Each topic uses ~2 API calls (syllabus + intro content).
TRENDING_TOPICS = [
    "Introduction to Artificial Intelligence",
    "Python Programming for Beginners",
]

async def pregenerate_trending():
    """Background task to pre-warm the cache for popular topics."""
    logger.info("Starting background pre-generation for trending topics...")
    db = SessionLocal()
    try:
        for topic in TRENDING_TOPICS:
            try:
                # 1. Pre-generate Syllabus
                cached_syllabus = await course_cache.get(topic)
                if not cached_syllabus:
                    logger.info(f"Pre-generating syllabus for: {topic}")
                    await generate_course_syllabus(topic, "Beginner", db, user_id=None)
                
                # 2. Pre-generate First Topic Content (Introduction)
                cached_content = await topic_cache.get(topic)
                if not cached_content:
                    logger.info(f"Pre-generating introduction content for: {topic}")
                    await generate_topic_content(
                        course_title=topic,
                        module_title="Introduction",
                        topic_title=topic,
                        level="Beginner",
                        db=db,
                        user_id=None
                    )
                
                # Generous delay to avoid burning API quota
                await asyncio.sleep(15)
                
            except Exception as e:
                logger.error(f"Failed to pre-generate {topic}: {e}")
                continue
                
    finally:
        db.close()
    logger.info("Finished background pre-generation cycle.")

async def start_pregen_worker():
    """Loop that runs every 24 hours."""
    while True:
        await pregenerate_trending()
        # Sleep for 24 hours
        await asyncio.sleep(86400)
