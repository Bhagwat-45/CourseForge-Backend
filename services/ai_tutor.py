"""
AI Tutor service for answering questions about courses
"""
import os
from typing import List, Dict, Optional
import google.generativeai as genai
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.models import Course, Lesson, Module

# Initialize Google Gemini client
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
else:
    model = None


class AITutor:
    """AI tutor that answers questions about course content"""
    
    async def get_response(
        self,
        course_id: int,
        user_message: str,
        conversation_history: List[Dict],
        db: Session
    ) -> str:
        """Get AI tutor response to user question"""
        
        # Get course context
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            return "I'm sorry, I couldn't find the course."
        
        # Build course context
        context = self._build_course_context(course, db)
        
        if not model:
            # Fallback response
            return f"I'm here to help with '{course.title}'. Based on the course content, I can provide explanations and answer questions. Please ask me anything about the course!"
        
        try:
            # Build conversation context for Gemini
            conversation_context = f"""You are an AI tutor helping students learn from this course: "{course.title}".

Course Context:
{context}

Your role:
- Answer questions clearly and helpfully
- Reference specific lessons and modules when relevant
- Provide examples and analogies when helpful
- Encourage learning and clarify concepts
- If asked about something not in the course, say so politely

Conversation History:
"""
            
            # Add conversation history
            for msg in conversation_history[-10:]:  # Last 10 messages
                role = msg.get("role", "user")
                content = msg.get("content", "")
                conversation_context += f"{role.capitalize()}: {content}\n\n"
            
            # Add current user message
            conversation_context += f"User: {user_message}\n\nAssistant:"
            
            # Get AI response
            response = model.generate_content(conversation_context)
            
            return response.text
            
        except Exception as e:
            print(f"Error getting AI tutor response: {e}")
            return "I'm sorry, I encountered an error. Please try again."
    
    def _build_course_context(self, course: Course, db: Session) -> str:
        """Build context string from course content"""
        context_parts = [f"Course: {course.title}"]
        
        if course.description:
            context_parts.append(f"Description: {course.description}")
        
        # Add module and lesson summaries
        for module in sorted(course.modules, key=lambda m: m.order):
            context_parts.append(f"\nModule {module.order}: {module.title}")
            if module.description:
                context_parts.append(f"  {module.description}")
            
            for lesson in sorted(module.lessons, key=lambda l: l.order):
                context_parts.append(f"  Lesson {lesson.order}: {lesson.title}")
                if lesson.summary:
                    context_parts.append(f"    Summary: {lesson.summary[:200]}")
                if lesson.beginner_content:
                    context_parts.append(f"    Content preview: {lesson.beginner_content[:300]}...")
        
        return "\n".join(context_parts)

