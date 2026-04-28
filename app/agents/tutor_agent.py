import os
from typing import List, Optional
from app.core.llm import invoke_with_retry

SYSTEM_PROMPT = """You are 'Nova', the elite AI Teaching Assistant for CourseForge.
Your goal is to help students achieve absolute mastery. You are encouraging, highly technical when needed, and deeply context-aware.

CRITICAL INSTRUCTIONS:
1. LONG-TERM COHERENCE: Always reference the specific module ({module_title}) and lesson content. If the student asks about a concept, try to link it back to earlier modules if relevant ("Recall how we discussed X in earlier modules...").
2. CITATION MODEL: When explaining a concept, explicitly cite the current lesson content provided in the context.
3. DEEP & EASY MASTERY:
   - Use the "Deep & Easy" philosophy: Explain the "what," "how," and "why" in every response.
   - Keep language simple and accessible, but never skip the technical depth.
   - Use rich analogies and exhaustive detail to ensure absolute mastery.
4. STABILITY & TRUTH: If the provided topic content is missing or insufficient to answer, provide a general pedagogical explanation but clearly state: "This isn't explicitly in the lesson, but here is the general principle..."
5. MASTERY CHECK: Occasionally end your response with a thought-provoking "Mastery Question" related to the current topic to keep the student engaged.
"""

def get_mentor_response(
    course_title: str = "Tutor",
    module_title: str = "",
    topic_title: str = "General",
    topic_content: str = "",
    level: str = "",
    user_query: str = "",
    chat_history: Optional[List[dict]] = None,
    current_context: str = "",
    model: str = "gemini-2.5-flash"
) -> str:
    if chat_history is None:
        chat_history = []
    """
    Generates a highly contextual contextual response from the Nova AI.
    """
    
    context = (
        f"Course: {course_title} (Level: {level})\n"
        f"Current Module: {module_title}\n"
        f"Current Topic: {topic_title}\n\n"
        f"Topic Content Reference:\n{topic_content}\n"
    )
    
    # Build prompt with history
    full_prompt = f"Here is the context for our session:\n{context}\n\nChat History:\n"
    for msg in chat_history:
        role = "Student" if msg['role'] == 'user' else "Nova"
        full_prompt += f"{role}: {msg['content']}\n"
    
    full_prompt += f"\nStudent: {user_query}\n"

    # Use Pro for tutor to ensure it can handle massive pasted code explanations accurately
    return invoke_with_retry(
        prompt=full_prompt,
        system_instruction=SYSTEM_PROMPT,
        model_name="gemini-2.5-flash"
    )
