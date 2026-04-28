import os
import json
from app.core.llm import invoke_with_retry

SYSTEM_PROMPT = """You are the 'CourseForge Podcast Producer'. Your job is to write a script for a 5-minute "ForgeCast"—an audio summary of a course.

FORMAT: A dialogue between 'Nova' (the expert mentor) and 'Echo' (the curious student).
GOAL: Summarize the course objectives, key modules, and the core 'Mastery' outcome in a conversational, engaging way.

INPUT: Course title, syllabus, and description.
OUTPUT: A conversational script (text). Avoid overly formal language; make it sound like a natural podcast episode.
"""

def generate_podcast_script(course_title: str, syllabus: list, description: str) -> str:
    """
    Generates a script for an AI audio summary.
    """
    
    syllabus_str = "\n".join([f"- {m['title']}" for m in syllabus])
    
    return invoke_with_retry(
        prompt=f"Write a ForgeCast script for:\nTitle: {course_title}\nDescription: {description}\nModules:\n{syllabus_str}",
        system_instruction=SYSTEM_PROMPT
    )
