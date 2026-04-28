import os
import json
from app.core.llm import invoke_with_retry

SYSTEM_PROMPT = """You are the 'Sync Optimizer' for CourseForge. Your job is to create a realistic day-by-day learning schedule for a course.
Analyze the course title, modules, and number of topics.
Assume the user studies for 1 hour per day.
Return ONLY an array of objects representng days:
[
  { "day": 1, "task": "Learn Module 1: Topics 1-3", "milestone": "Foundation laid" },
  { "day": 2, "task": "...", "milestone": "..." }
]
"""

def generate_study_schedule(course_title: str, modules_data: list) -> list:
    """
    Generates a day-by-day study schedule based on course content.
    """
    
    course_summary = f"Course: {course_title}\n"
    for i, mod in enumerate(modules_data):
        course_summary += f"Module {i+1}: {mod['title']} ({len(mod.get('topics', []))} topics)\n"

    content = invoke_with_retry(
        prompt=f"Create a schedule for:\n{course_summary}",
        system_instruction=SYSTEM_PROMPT
    )

    try:
        # Extract JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        return json.loads(content)
    except Exception as e:
        print(f"Failed to parse schedule: {e}")
        # Default fallback schedule if AI fails
        return [{"day": 1, "task": "Introduction to the course", "milestone": "Started"}]
