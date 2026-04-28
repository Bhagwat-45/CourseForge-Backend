import asyncio
import logging
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.models import Topic
from app.agents.topic_agent import generate_topic_content
from app.core.redis_client import redis_client
from app.core.metrics import metrics

logger = logging.getLogger(__name__)

@celery_app.task(name="app.tasks.ai_tasks.generate_topic_task", bind=True, max_retries=3)
def generate_topic_task(self, topic_id: int):
    """
    Celery task to generate topic content.
    Prevents duplicate jobs via Redis and updates DB status.
    """
    db = SessionLocal()
    lock_key = f"job:topic:{topic_id}"
    
    try:
        # 1. Check/Set Distributed Lock with 10-minute safety TTL
        if redis_client:
            # use set with nx=True and ex=600 for atomic lock creation with TTL
            if not redis_client.set(lock_key, "running", nx=True, ex=600):
                logger.warning(f"Task already running for topic {topic_id}. Skipping.")
                return {"status": "already_running"}

        # 2. Fetch Topic
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            logger.error(f"Topic {topic_id} not found.")
            return {"status": "error", "message": "Topic not found"}

        # 3. Update Status
        topic.generation_status = "generating"
        db.commit()

        # 4. Run AI Agent (Async wrapper)
        async def run_agent():
            return await generate_topic_content(
                course_title=topic.module.course.title,
                module_title=topic.module.title,
                topic_title=topic.title,
                level="Beginner", # Can be parameterized later
                db=db,
                user_id=topic.module.course.owner_id
            )

        loop = asyncio.get_event_loop()
        content_data = loop.run_until_complete(run_agent())

        # 5. Update Topic with Results
        topic.beginner_content = content_data["beginner_content"]
        topic.intermediate_content = content_data["intermediate_content"]
        topic.expert_content = content_data["expert_content"]
        topic.examples = content_data["examples"]
        topic.analogies = content_data["analogies"]
        topic.summary = content_data["summary"]
        topic.quizzes = content_data["quizzes"]
        topic.flashcards = content_data["flashcards"]
        topic.generation_status = "ready"
        
        db.commit()
        logger.info(f"Successfully generated content for topic {topic_id}")
        
        # 6. Notify WebSockets via Redis Pub/Sub
        if redis_client:
            redis_client.publish("topic_updates", json.dumps({
                "topic_id": topic_id,
                "status": "ready",
                "message": "Content is ready"
            }))
        
        return {"status": "success", "topic_id": topic_id}
        
    except Exception as exc:
        logger.error(f"Celery task failed for topic {topic_id}: {exc}")
        
        # Update status to failed
        try:
            topic = db.query(Topic).filter(Topic.id == topic_id).first()
            if topic:
                topic.generation_status = "failed"
                db.commit()
                if redis_client:
                    redis_client.publish("topic_updates", json.dumps({
                        "topic_id": topic_id,
                        "status": "failed",
                        "message": str(exc)
                    }))
        except: pass

        # Retry logic for network/AI errors
        raise self.retry(exc=exc, countdown=10) # 10s wait before retry
        
    finally:
        db.close()
        # Release lock
        if redis_client:
            redis_client.delete(lock_key)
