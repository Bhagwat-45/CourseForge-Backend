from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import User, Course, Topic
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/metrics")
def get_platform_metrics(db: Session = Depends(get_db)):
    """Yields top-level SaaS observability using fast, lightweight count queries."""
    # Lightweight `.count()` prevents heavy joins
    users = db.query(User).count()
    courses = db.query(Course).count()
    topics = db.query(Topic).count()
    
    return {
        "total_users": users,
        "total_courses": courses,
        "total_ai_generations": topics + courses 
    }
