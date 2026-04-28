"""
Course retrieval and management endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.core.database import get_db
from app.models import Course

router = APIRouter()

@router.get("/courses")
async def list_courses(db: Session = Depends(get_db)):
    courses = db.query(Course).order_by(Course.created_at.desc()).all()
    return {
        "courses": [
            {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "source_type": course.source_type,
                "created_at": course.created_at.isoformat() if course.created_at else None,
                "module_count": len(course.modules)
            }
            for course in courses
        ]
    }

@router.get("/courses/{course_id}")
async def get_course(course_id: int, db: Session = Depends(get_db)):
    """Get full course details with all modules, lessons, and content"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    modules_data = []
    for module in sorted(course.modules, key=lambda m: m.order):
        lessons_data = []
        for lesson in sorted(module.lessons, key=lambda l: l.order):
            quizzes_data = [
                {
                    "id": quiz.id,
                    "question": quiz.question,
                    "options": quiz.options,
                    "correct_answer": quiz.correct_answer,
                    "explanation": quiz.explanation
                }
                for quiz in lesson.quizzes
            ]
            
            lessons_data.append({
                "id": lesson.id,
                "title": lesson.title,
                "order": lesson.order,
                "beginner_content": lesson.beginner_content,
                "intermediate_content": lesson.intermediate_content,
                "expert_content": lesson.expert_content,
                "examples": lesson.examples or [],
                "analogies": lesson.analogies or [],
                "diagrams": lesson.diagrams or [],
                "summary": lesson.summary,
                "coding_tasks": lesson.coding_tasks or [],
                "quizzes": quizzes_data
            })
        
        modules_data.append({
            "id": module.id,
            "title": module.title,
            "description": module.description,
            "order": module.order,
            "lessons": lessons_data
        })
    
    flashcards_data = [
        {
            "id": flashcard.id,
            "front": flashcard.front,
            "back": flashcard.back
        }
        for flashcard in course.flashcards
    ]
    
    return {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "source_type": course.source_type,
        "table_of_contents": course.table_of_contents,
        "modules": modules_data,
        "flashcards": flashcards_data,
        "created_at": course.created_at.isoformat() if course.created_at else None
    }

@router.get("/courses/{course_id}/toc")
async def get_table_of_contents(course_id: int, db: Session = Depends(get_db)):
    """Get table of contents for a course"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    return {
        "course_id": course.id,
        "title": course.title,
        "table_of_contents": course.table_of_contents
    }

@router.get("/courses/{course_id}/flashcards")
async def get_flashcards(course_id: int, db: Session = Depends(get_db)):
    """Get all flashcards for a course"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    flashcards = [
        {
            "id": flashcard.id,
            "front": flashcard.front,
            "back": flashcard.back
        }
        for flashcard in course.flashcards
    ]
    
    return {"flashcards": flashcards}

@router.delete("/courses/{course_id}")
async def delete_course(course_id: int, db: Session = Depends(get_db)):
    """Delete a course"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    db.delete(course)
    db.commit()
    
    return {"success": True, "message": "Course deleted"}