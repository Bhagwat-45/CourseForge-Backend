"""
Course export endpoints — Markdown and JSON downloads.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.models import User, Course, Module, Topic

router = APIRouter()


def _build_course_dict(course: Course, db: Session) -> dict:
    """Build a full nested dictionary for a course."""
    modules = db.query(Module).filter(Module.course_id == course.id).order_by(Module.order).all()
    modules_data = []
    for mod in modules:
        topics = db.query(Topic).filter(Topic.module_id == mod.id).order_by(Topic.order).all()
        topics_data = []
        for t in topics:
            topics_data.append({
                "id": t.id,
                "title": t.title,
                "order": t.order,
                "beginner_content": t.beginner_content or "",
                "intermediate_content": t.intermediate_content or "",
                "expert_content": t.expert_content or "",
                "examples": t.examples or [],
                "analogies": t.analogies or [],
                "summary": t.summary or "",
            })
        modules_data.append({
            "id": mod.id,
            "title": mod.title,
            "description": mod.description or "",
            "order": mod.order,
            "topics": topics_data,
        })
    return {
        "id": course.id,
        "title": course.title,
        "description": course.description or "",
        "difficulty": str(course.difficulty.value) if course.difficulty else "starter",
        "modules": modules_data,
    }


def _build_markdown(course_dict: dict) -> str:
    """Convert course dict to a formatted Markdown document."""
    lines = []
    lines.append(f"# {course_dict['title']}\n")
    lines.append(f"*{course_dict['description']}*\n")
    lines.append(f"**Difficulty:** {course_dict['difficulty'].capitalize()}\n")
    lines.append("---\n")

    for mod in course_dict["modules"]:
        lines.append(f"## Module {mod['order'] + 1}: {mod['title']}\n")
        if mod["description"]:
            lines.append(f"{mod['description']}\n")

        for topic in mod["topics"]:
            lines.append(f"### {topic['title']}\n")

            if topic["beginner_content"]:
                lines.append("#### Beginner Level\n")
                lines.append(f"{topic['beginner_content']}\n")

            if topic["intermediate_content"]:
                lines.append("#### Intermediate Level\n")
                lines.append(f"{topic['intermediate_content']}\n")

            if topic["expert_content"]:
                lines.append("#### Expert Level\n")
                lines.append(f"{topic['expert_content']}\n")

            if topic["examples"]:
                lines.append("#### Examples\n")
                for ex in topic["examples"]:
                    lines.append(f"- {ex}\n")
                lines.append("")

            if topic["analogies"]:
                lines.append("#### Analogies\n")
                for an in topic["analogies"]:
                    lines.append(f"- {an}\n")
                lines.append("")

            if topic["summary"]:
                lines.append(f"**Summary:** {topic['summary']}\n")

            lines.append("---\n")

    return "\n".join(lines)


@router.get("/{course_id}/export/markdown")
def export_course_markdown(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export a full course as a Markdown file."""
    course = db.query(Course).filter(
        Course.id == course_id, Course.owner_id == current_user.id
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    course_dict = _build_course_dict(course, db)
    md_content = _build_markdown(course_dict)

    safe_title = course.title.replace(" ", "_").replace("/", "-")[:50]
    filename = f"{safe_title}.md"

    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{course_id}/export/json")
def export_course_json(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export a full course as structured JSON."""
    course = db.query(Course).filter(
        Course.id == course_id, Course.owner_id == current_user.id
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return _build_course_dict(course, db)
