"""
Global search endpoint — searches across courses, modules, and topics.
"""
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.models import User, Course, Module, Topic

router = APIRouter()


@router.get("/")
def global_search(
    q: str = Query(..., min_length=1, description="Search query"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search across courses, modules, and topics owned by the current user.
    Returns categorized results. Safely handles database failures.
    """
    try:
        pattern = f"%{q}%"

        # Search courses
        courses = (
            db.query(Course)
            .filter(Course.owner_id == current_user.id)
            .filter(
                (Course.title.ilike(pattern)) | (Course.description.ilike(pattern))
            )
            .limit(10)
            .all()
        )

        # Search modules (only within user's courses)
        modules = (
            db.query(Module)
            .join(Course)
            .filter(Course.owner_id == current_user.id)
            .filter(Module.title.ilike(pattern))
            .limit(10)
            .all()
        )

        # Search topics (only within user's courses)
        topics = (
            db.query(Topic)
            .join(Module)
            .join(Course)
            .filter(Course.owner_id == current_user.id)
            .filter(Topic.title.ilike(pattern))
            .limit(15)
            .all()
        )

        return {
            "query": q,
            "results": {
                "courses": [
                    {
                        "id": c.id,
                        "title": c.title,
                        "description": c.description or "",
                        "type": "course",
                    }
                    for c in courses
                ],
                "modules": [
                    {
                        "id": m.id,
                        "title": m.title,
                        "course_id": m.course_id,
                        "type": "module",
                    }
                    for m in modules
                ],
                "topics": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "module_id": t.module_id,
                        "course_id": t.module.course_id if t.module else None,
                        "type": "topic",
                    }
                    for t in topics
                ],
            },
            "total": len(courses) + len(modules) + len(topics),
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[DB_ERROR] operation=global_search reason=\"{str(e)}\"")
        return {
            "query": q,
            "results": {"courses": [], "modules": [], "topics": []},
            "total": 0
        }
