from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.models import User
from app.services import srs_engine
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter()

class ReviewSubmit(BaseModel):
    flashcard_id: int
    quality: int

@router.get("/daily-review")
async def get_daily_reviews(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch due flashcards for the user's daily review."""
    reviews = srs_engine.get_due_cards(db, current_user.id, limit)
    return {"reviews": reviews, "count": len(reviews)}

@router.post("/review")
async def submit_review(
    review: ReviewSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a flashcard review rating (0-5)."""
    try:
        result = srs_engine.review_card(db, current_user.id, review.flashcard_id, review.quality)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/init-course/{course_id}")
async def init_course_srs(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initialize SRS records for all flashcards in a course."""
    try:
        count = srs_engine.init_srs_for_course(db, current_user.id, course_id)
        return {"status": "success", "initialized_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
