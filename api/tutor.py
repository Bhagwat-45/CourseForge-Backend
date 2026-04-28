"""
AI Tutor endpoints for Q&A
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.core.database import get_db
from app.models import Course, TutorConversation
from services.ai_tutor import AITutor
from typing import List, Optional

router = APIRouter()


class TutorMessage(BaseModel):
    message: str
    user_id: Optional[str] = "default"


class TutorResponse(BaseModel):
    response: str
    conversation_id: int


@router.post("/tutor/{course_id}/chat")
async def chat_with_tutor(
    course_id: int,
    tutor_message: TutorMessage,
    db: Session = Depends(get_db)
):
    """Chat with AI tutor about the course"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Get or create conversation
    conversation = db.query(TutorConversation).filter(
        TutorConversation.course_id == course_id,
        TutorConversation.user_id == tutor_message.user_id
    ).first()
    
    if not conversation:
        conversation = TutorConversation(
            course_id=course_id,
            user_id=tutor_message.user_id,
            messages=[]
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    # Get AI tutor response
    tutor = AITutor()
    response = await tutor.get_response(
        course_id=course_id,
        user_message=tutor_message.message,
        conversation_history=conversation.messages,
        db=db
    )
    
    # Update conversation
    conversation.messages.append({"role": "user", "content": tutor_message.message})
    conversation.messages.append({"role": "assistant", "content": response})
    db.commit()
    
    return TutorResponse(response=response, conversation_id=conversation.id)


@router.get("/tutor/{course_id}/conversation")
async def get_conversation(
    course_id: int,
    user_id: str = "default",
    db: Session = Depends(get_db)
):
    """Get conversation history with tutor"""
    conversation = db.query(TutorConversation).filter(
        TutorConversation.course_id == course_id,
        TutorConversation.user_id == user_id
    ).first()
    
    if not conversation:
        return {"messages": []}
    
    return {
        "conversation_id": conversation.id,
        "messages": conversation.messages
    }

