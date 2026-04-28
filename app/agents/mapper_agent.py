import os
import json
from app.core.llm import invoke_with_retry

SYSTEM_PROMPT = """You are the 'CourseForge Cartographer'. Your job is to analyze a collection of courses and find semantic connections between them.

INPUT: A list of course titles and their descriptions.
OUTPUT: A JSON object containing:
1. "nodes": A list of all course IDs with their titles and categories.
2. "links": A list of objects { "source": course_id, "target": course_id, "label": "Reason for connection" }.

Rules:
- Only create links where a genuine educational or topical overlap exists.
- Be concise with link labels (e.g., "Advanced Algebra overlap", "Shared UI/UX principles").
- Ensure the output is valid JSON.
"""

def generate_knowledge_graph(courses: list) -> dict:
    """
    Analyzes multiple courses to create a graph of semantic connections.
    courses: List of objects with id, title, description, category.
    """
    if not courses:
        return {"nodes": [], "links": []}

    course_data = "\n".join([
        f"ID: {c['id']} | Title: {c['title']} | Category: {c['category']} | Desc: {c['description']}" 
        for c in courses
    ])
    
    content = invoke_with_retry(
        prompt=f"Analyze these courses and generate a semantic graph:\n{course_data}",
        system_instruction=SYSTEM_PROMPT
    )
    
    try:
        if "```json" in content: content = content.split("```json")[1].split("```")[0].strip()
        return json.loads(content)
    except Exception as e:
        print(f"Mapper Agent error: {e}")
        # Fallback: Just return nodes without links
        return {
            "nodes": courses,
            "links": []
        }
