from sqlalchemy.orm import Session
from app.models.models import ActivityLog

def log_action(db: Session, user_id: int | None, action: str, details: dict = None):
    """
    Quietly adds a system event to the activity_logs table.
    Note: Does NOT call db.commit() to preserve parent transaction boundaries.
    """
    log_entry = ActivityLog(
        user_id=user_id,
        activity_type=action,
        activity_metadata=details or {}
    )
    db.add(log_entry)
