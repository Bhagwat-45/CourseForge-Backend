"""
Export functionality for courses (summaries, notes, flashcards)
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.core.database import get_db
from app.models import Course
import json

router = APIRouter()


@router.get("/courses/{course_id}/export/summary")
async def export_summary(course_id: int, db: Session = Depends(get_db)):
    """Export course summary as text"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    summary_lines = [f"# {course.title}\n"]
    if course.description:
        summary_lines.append(f"{course.description}\n\n")
    
    for module in sorted(course.modules, key=lambda m: m.order):
        summary_lines.append(f"## {module.title}\n")
        if module.description:
            summary_lines.append(f"{module.description}\n\n")
        
        for lesson in sorted(module.lessons, key=lambda l: l.order):
            summary_lines.append(f"### {lesson.title}\n")
            if lesson.summary:
                summary_lines.append(f"{lesson.summary}\n\n")
    
    content = "\n".join(summary_lines)
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=course_{course_id}_summary.txt"}
    )


@router.get("/courses/{course_id}/export/flashcards")
async def export_flashcards(
    course_id: int,
    format: str = "json",
    db: Session = Depends(get_db)
):
    """Export flashcards in JSON or CSV format"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    flashcards = course.flashcards
    
    if format == "csv":
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Front", "Back"])
        
        for flashcard in flashcards:
            writer.writerow([flashcard.front, flashcard.back])
        
        content = output.getvalue()
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=course_{course_id}_flashcards.csv"}
        )
    else:
        # JSON format
        data = [
            {"front": f.front, "back": f.back}
            for f in flashcards
        ]
        content = json.dumps(data, indent=2)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=course_{course_id}_flashcards.json"}
        )


@router.get("/courses/{course_id}/export/notes")
async def export_notes(course_id: int, db: Session = Depends(get_db)):
    """Export all course content as notes (Markdown)"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    notes_lines = [f"# {course.title}\n\n"]
    if course.description:
        notes_lines.append(f"{course.description}\n\n")
    
    for module in sorted(course.modules, key=lambda m: m.order):
        notes_lines.append(f"## {module.title}\n\n")
        if module.description:
            notes_lines.append(f"{module.description}\n\n")
        
        for lesson in sorted(module.lessons, key=lambda l: l.order):
            notes_lines.append(f"### {lesson.title}\n\n")
            
            if lesson.intermediate_content:
                notes_lines.append(f"{lesson.intermediate_content}\n\n")
            elif lesson.beginner_content:
                notes_lines.append(f"{lesson.beginner_content}\n\n")
            elif lesson.expert_content:
                notes_lines.append(f"{lesson.expert_content}\n\n")
            
            if lesson.examples:
                notes_lines.append("#### Examples\n\n")
                for example in lesson.examples:
                    notes_lines.append(f"- {example}\n")
                notes_lines.append("\n")
            
            if lesson.summary:
                notes_lines.append(f"**Summary:** {lesson.summary}\n\n")
    
    content = "\n".join(notes_lines)
    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=course_{course_id}_notes.md"}
    )

