"""
Discussion Threads API — per-topic community Q&A.
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_current_user, get_db
from app.models.models import User, Discussion, Topic
from app.core.gamification import award_xp, check_and_award_badges

router = APIRouter()


class DiscussionCreate(BaseModel):
    content: str
    parent_id: Optional[int] = None


@router.get("/{topic_id}")
def get_discussions(
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all top-level discussions for a topic with their replies."""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Get top-level messages (no parent)
    top_level = db.query(Discussion).filter(
        Discussion.topic_id == topic_id,
        Discussion.parent_id == None,
    ).order_by(Discussion.created_at.desc()).all()

    def serialize(msg):
        replies = db.query(Discussion).filter(
            Discussion.parent_id == msg.id
        ).order_by(Discussion.created_at.asc()).all()

        return {
            "id": msg.id,
            "content": msg.content,
            "author": msg.user.name if msg.user else "Anonymous",
            "user_id": msg.user_id,
            "upvotes": msg.upvotes,
            "created_at": str(msg.created_at),
            "replies": [serialize(r) for r in replies],
        }

    return [serialize(m) for m in top_level]


@router.post("/{topic_id}")
def post_discussion(
    topic_id: int,
    payload: DiscussionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Post a new discussion message or reply."""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    if not payload.content or not payload.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")

    # If this is a reply, verify parent exists
    if payload.parent_id:
        parent = db.query(Discussion).filter(Discussion.id == payload.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent message not found")

    msg = Discussion(
        topic_id=topic_id,
        user_id=current_user.id,
        content=payload.content.strip(),
        parent_id=payload.parent_id,
    )
    db.add(msg)
    
    # Award XP for participation
    award_xp(db, current_user, 5)
    check_and_award_badges(db, current_user)
    
    db.commit()
    db.refresh(msg)

    return {
        "id": msg.id,
        "content": msg.content,
        "author": current_user.name,
        "user_id": current_user.id,
        "upvotes": 0,
        "created_at": str(msg.created_at),
        "replies": [],
    }


@router.post("/{message_id}/upvote")
def upvote_discussion(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upvote a discussion message."""
    msg = db.query(Discussion).filter(Discussion.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    msg.upvotes += 1
    
    # Award XP to the author of the upvoted post
    if msg.user:
        award_xp(db, msg.user, 10)
        check_and_award_badges(db, msg.user)
        
    db.commit()

    return {"id": msg.id, "upvotes": msg.upvotes}
