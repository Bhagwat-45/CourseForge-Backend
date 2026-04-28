import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Initialize Celery
# The broker and backend are typically Redis in this architecture
celery_app = Celery(
    "courseforge",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    include=["app.tasks.ai_tasks"] # We will create this next
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300, # 5 minutes max per AI job
    task_acks_late=True, # Ensure task is acknowledged only after completion
    task_reject_on_worker_lost=True, # Re-queue if worker crashes
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
)

if __name__ == "__main__":
    celery_app.start()
