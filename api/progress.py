"""
Course progress tracking endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.core.database import get_db
from app.models import Course, CourseProgress, Lesson, Module
from typing import List, Optional

router = APIRouter()


class ProgressUpdate(BaseModel):
    lesson_id: int
    completed: bool
    user_id: Optional[str] = "default"


class QuizScore(BaseModel):
    quiz_id: int
    score: float
    user_id: Optional[str] = "default"


@router.get("/progress/{course_id}")
async def get_progress(
    course_id: int,
    user_id: str = "default",
    db: Session = Depends(get_db)
):
    """Get user's progress for a course"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    progress = db.query(CourseProgress).filter(
        CourseProgress.course_id == course_id,
        CourseProgress.user_id == user_id
    ).first()
    
    if not progress:
        # Create initial progress
        progress = CourseProgress(
            course_id=course_id,
            user_id=user_id,
            completed_lessons=[],
            quiz_scores={},
            overall_progress=0.0
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)
    
    return {
        "course_id": course_id,
        "user_id": user_id,
        "current_module_id": progress.current_module_id,
        "current_lesson_id": progress.current_lesson_id,
        "completed_lessons": progress.completed_lessons or [],
        "quiz_scores": progress.quiz_scores or {},
        "overall_progress": progress.overall_progress
    }


@router.post("/progress/{course_id}/lesson")
async def update_lesson_progress(
    course_id: int,
    progress_update: ProgressUpdate,
    db: Session = Depends(get_db)
):
    """Update lesson completion status"""
    progress = db.query(CourseProgress).filter(
        CourseProgress.course_id == course_id,
        CourseProgress.user_id == progress_update.user_id
    ).first()
    
    if not progress:
        progress = CourseProgress(
            course_id=course_id,
            user_id=progress_update.user_id,
            completed_lessons=[],
            quiz_scores={}
        )
        db.add(progress)
    
    completed = progress.completed_lessons or []
    if progress_update.completed:
        if progress_update.lesson_id not in completed:
            completed.append(progress_update.lesson_id)
    else:
        if progress_update.lesson_id in completed:
            completed.remove(progress_update.lesson_id)
    
    progress.completed_lessons = completed
    
    # Calculate overall progress
    course = db.query(Course).filter(Course.id == course_id).first()
    total_lessons = sum(len(module.lessons) for module in course.modules)
    if total_lessons > 0:
        progress.overall_progress = len(completed) / total_lessons
    
    db.commit()
    
    return {
        "success": True,
        "completed_lessons": completed,
        "overall_progress": progress.overall_progress
    }


@router.post("/progress/{course_id}/quiz")
async def update_quiz_score(
    course_id: int,
    quiz_score: QuizScore,
    db: Session = Depends(get_db)
):
    """Update quiz score"""
    progress = db.query(CourseProgress).filter(
        CourseProgress.course_id == course_id,
        CourseProgress.user_id == quiz_score.user_id
    ).first()
    
    if not progress:
        progress = CourseProgress(
            course_id=course_id,
            user_id=quiz_score.user_id,
            completed_lessons=[],
            quiz_scores={}
        )
        db.add(progress)
    
    scores = progress.quiz_scores or {}
    scores[str(quiz_score.quiz_id)] = quiz_score.score
    progress.quiz_scores = scores
    
    db.commit()
    
    return {
        "success": True,
        "quiz_scores": scores
    }

