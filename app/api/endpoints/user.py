from typing import Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_current_user, get_db
from app.agents.mapper_agent import generate_knowledge_graph
from app.core.cache import knowledge_map_cache
from app.core import security
from app.models.models import User, Course, Topic, Module, CourseProgress, Flashcard, ActivityLog
from app.schemas.user import User as UserSchema
from app.services import srs_engine
from datetime import datetime, timedelta

router = APIRouter()


# ── Pydantic models for profile updates ──────────────────────────────
class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.get("/stats", response_model=UserSchema)
def get_user_stats(
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get current user's learning stats (XP, streaks, etc.)
    """
    return current_user

@router.get("/summary")
@router.get("/learning-summary")
def get_learning_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculates overall progress across all courses."""
    try:
        courses = db.query(Course).filter(Course.owner_id == current_user.id).all()
        if not courses:
            return {
                "average_progress": 0,
                "total_courses": 0,
                "total_topics_done": 0,
                "xp": current_user.xp if current_user else 0,
                "streak_days": current_user.streak_days if current_user else 0,
            }
        
        total_percentage = 0
        total_topics_done = 0
        for course in courses:
            progress = db.query(CourseProgress).filter(
                CourseProgress.user_id == current_user.id,
                CourseProgress.course_id == course.id
            ).first()
            
            num_completed = len(progress.completed_topic_ids) if progress and progress.completed_topic_ids else 0
            total_topics_done += num_completed

            all_topics_count = db.query(Topic).join(Module).filter(Module.course_id == course.id).count()
            if all_topics_count > 0:
                total_percentage += (num_completed / all_topics_count) * 100

        return {
            "average_progress": round(total_percentage / len(courses), 1) if courses else 0,
            "total_courses": len(courses),
            "total_topics_done": total_topics_done,
            "xp": current_user.xp if current_user else 0,
            "streak_days": current_user.streak_days if current_user else 0,
        }
    except Exception as e:
        import traceback
        import logging
        logging.getLogger(__name__).error(f"[SYSTEM_ERROR] endpoint=/summary error=\"{str(e)}\"")
        return {
            "average_progress": 0,
            "total_courses": 0,
            "total_topics_done": 0,
            "xp": current_user.xp if getattr(current_user, 'xp', None) else 0,
            "streak_days": current_user.streak_days if getattr(current_user, 'streak_days', None) else 0,
        }

@router.get("/leaderboard")
def get_leaderboard(db: Session = Depends(get_db)):
    """Return top users by XP for the global leaderboard."""
    users = db.query(User).order_by(User.xp.desc()).limit(10).all()
    
    leaderboard = []
    for user in users:
        # Level calculation: floor(sqrt(XP / 100)) + 1
        level = int((user.xp / 100) ** 0.5) + 1
        leaderboard.append({
            "name": user.name,
            "xp": user.xp,
            "level": level,
            "streak": user.streak_days
        })
    return leaderboard


@router.put("/profile")
def update_profile(
    updates: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the current user's profile (name, age)."""
    if updates.name is not None:
        current_user.name = updates.name
    if updates.age is not None:
        current_user.age = updates.age
    db.commit()
    db.refresh(current_user)
    return {
        "status": "updated",
        "name": current_user.name,
        "age": current_user.age,
        "email": current_user.email,
    }


@router.put("/password")
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change the current user's password."""
    if not security.verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    
    current_user.password_hash = security.get_password_hash(payload.new_password)
    db.commit()
    return {"status": "password_changed"}


@router.get("/knowledge-map")
def get_knowledge_map(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates a semantic knowledge graph of all user courses."""
    courses = db.query(Course).filter(Course.owner_id == current_user.id).all()
    
    course_list = [
        {
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "category": "General"
        } for c in courses
    ]
    
    # Try cache first
    cache_key = f"km_{current_user.id}_{len(course_list)}"
    cached_graph = knowledge_map_cache.get(cache_key)
    if cached_graph:
        return cached_graph

    graph = generate_knowledge_graph(course_list)
    knowledge_map_cache.set(cache_key, graph)
    return graph


@router.get("/activity-data")
def get_activity_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns activity counts for the last 365 days grouped by date."""
    one_year_ago = datetime.now() - timedelta(days=365)
    
    activities = db.query(
        func.date(ActivityLog.created_at).label("date"),
        func.count(ActivityLog.id).label("count")
    ).filter(
        ActivityLog.user_id == current_user.id,
        ActivityLog.created_at >= one_year_ago
    ).group_by(
        func.date(ActivityLog.created_at)
    ).all()
    
    return [{"date": str(a.date), "count": a.count} for a in activities]


# ── Spaced Repetition Endpoints ──────────────────────────────────────
@router.get("/flashcards/due")
def get_due_flashcards(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get flashcards due for review today."""
    cards = srs_engine.get_due_cards(db, current_user.id)
    return {"due_count": len(cards), "cards": cards}


@router.post("/flashcards/{flashcard_id}/review")
def review_flashcard(
    flashcard_id: int,
    quality: int = 4,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a review rating for a flashcard (quality: 0-5)."""
    card = db.query(Flashcard).filter(Flashcard.id == flashcard_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    
    result = srs_engine.review_card(db, current_user.id, flashcard_id, quality)
    return result


@router.post("/flashcards/init/{course_id}")
def init_course_srs(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Initialize SRS tracking for all flashcards in a course."""
    new_count = srs_engine.init_srs_for_course(db, current_user.id, course_id)
    return {"initialized": new_count}
