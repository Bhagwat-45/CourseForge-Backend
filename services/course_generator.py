"""
AI-powered course generation service
"""
import os
from typing import Dict, List, Optional
import google.generativeai as genai
from sqlalchemy.orm import Session
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.models import Course, Module, Lesson, Quiz, Flashcard

# Initialize Google Gemini client
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
else:
    model = None


class CourseGenerator:
    """Generates structured courses from content using AI"""
    
    async def generate_course(self, content: str, source_type: str, file_path: Optional[str] = None) -> Dict:
        """Generate a complete course structure from content"""
        
        if not model:
            # Fallback: create a simple course structure without AI
            return self._create_simple_course(content, source_type, file_path)
        
        # Use AI to generate course structure
        try:
            prompt = self._create_generation_prompt(content, source_type)
            
            # Combine system and user prompts for Gemini
            full_prompt = f"""You are an expert course creator. Generate structured educational content.

{prompt}"""
            
            response = model.generate_content(full_prompt)
            course_json = json.loads(response.text)
            return course_json
            
        except Exception as e:
            print(f"Error generating course with AI: {e}")
            # Fallback to simple course
            return self._create_simple_course(content, source_type, file_path)
    
    def _create_generation_prompt(self, content: str, source_type: str) -> str:
        """Create prompt for AI course generation"""
        # Detect if this is a broad topic request
        is_broad_topic = len(content) < 500 and (
            'full course' in content.lower() or
            'complete course' in content.lower() or
            'from basics' in content.lower() or
            'comprehensive' in content.lower()
        )
        
        # Truncate content if too long
        max_length = 20000
        if len(content) > max_length:
            content = content[:max_length] + "... [content truncated]"
        
        prompt_intro = f"""You are an expert course creator and curriculum designer. {'The user has requested a comprehensive course on a broad topic. Analyze the topic and create a complete, detailed syllabus covering all essential aspects from fundamentals to advanced concepts.' if is_broad_topic else 'Convert the following content into a comprehensive, well-structured educational course.'}

IMPORTANT: Generate meaningful, descriptive topic names - NEVER use generic names like "Topic 1", "Concept 1", "Introduction", "Basics".

Source type: {source_type}
Content/Request:
{content}

Generate a JSON structure with the following format:
{{
  "title": "Course Title",
  "description": "Comprehensive course description (2-3 sentences)",
  "table_of_contents": [
    {{"module": 1, "title": "Module Title", "lessons": ["Topic 1", "Topic 2"]}}
  ],
  "modules": [
    {{
      "title": "Module Title (e.g., 'Python Fundamentals', 'Control Flow', 'Data Structures')",
      "description": "Module description (1-2 sentences)",
      "order": 1,
      "lessons": [
        {{
          "title": "Specific Topic Name (e.g., 'Variables and Data Types', 'Installing Python & Running Your First Program', 'If-Else Statements') - NOT generic names",
          "order": 1,
          "beginner_content": "# Overview\n[Clear definition - 2-3 sentences]\n\n# Why This Matters\n[1-2 paragraphs explaining importance]\n\n# Step-by-Step Explanation\n[400-600 words: Break down concept into clear steps, use simple language, include examples, common mistakes, recap]",
          "intermediate_content": "# Deep Dive\n[Technical overview - 2-3 paragraphs]\n\n# How It Works Internally\n[Explain internal mechanisms - 2-3 paragraphs]\n\n# Advanced Concepts\n[500-800 words: Cover intermediate concepts, patterns, best practices, real-world use cases, performance considerations]",
          "expert_content": "# Architecture & Design\n[Deep architectural discussion - 2-3 paragraphs]\n\n# Internal Implementation Details\n[700-1000+ words: Explain implementation, memory management, optimization, advanced patterns, edge cases, production scenarios, industry standards]",
          "examples": ["Practical example 1", "Code example 2", "Real-world scenario 3"],
          "analogies": ["Creative analogy 1", "Relatable analogy 2"],
          "summary": "Concise summary (2-3 sentences)",
          "quizzes": [
            {{
              "questionText": "Multiple choice question",
              "type": "mcq",
              "options": ["Option A", "Option B (correct)", "Option C", "Option D"],
              "correct_answer": 1,
              "explanation": "Detailed explanation (2-3 sentences)",
              "difficulty": "Beginner"
            }},
            {{
              "questionText": "True or False: [Statement]",
              "type": "true_false",
              "options": ["True", "False"],
              "correct_answer": 0,
              "explanation": "Explanation",
              "difficulty": "Beginner"
            }},
            {{
              "questionText": "Complete the code: [Code snippet with blank]",
              "type": "code",
              "options": ["Code option A (correct)", "Code option B", "Code option C", "Code option D"],
              "correct_answer": 0,
              "explanation": "Code explanation",
              "difficulty": "Intermediate"
            }},
            {{
              "questionText": "Find the error in this code: [Code with error]",
              "type": "code",
              "options": ["Error description A (correct)", "Error description B", "Error description C", "No error"],
              "correct_answer": 0,
              "explanation": "Error explanation",
              "difficulty": "Intermediate"
            }}
          ],
          "coding_tasks": ["Task 1", "Task 2"]
        }}
      ]
    }}
  ],
  "flashcards": [
    {{"front": "Question", "back": "Answer"}}
  ]
}}

CRITICAL REQUIREMENTS:
1. Generate 4-10 modules (more for broad topics)
2. Each module should have 8-25 topics with MEANINGFUL, DESCRIPTIVE NAMES
3. Topic names MUST be specific: "Variables and Data Types", "Installing Python & Running Your First Program" - NOT "Topic 1", "Concept 1"
4. Beginner content: 400-600 words with Overview, Why This Matters, Step-by-Step, Examples, Common Mistakes, Recap
5. Intermediate content: 500-800 words with Deep Dive, How It Works, Advanced Concepts, Best Practices, Real-World Use Cases
6. Expert content: 700-1000+ words with Architecture, Implementation Details, Advanced Patterns, Edge Cases, Performance, Production Scenarios
7. Generate 5-10 quiz questions per topic with variety: MCQ (40-50%), True/False (20-30%), Code Completion (20-30%), Find Error (10-20%)
8. Each quiz question must have: questionText, type, options, correct_answer (index), explanation (2-3 sentences), difficulty (Beginner/Intermediate/Expert)
9. For broad topics, create complete curriculum from fundamentals to advanced
10. All content must be detailed, educational, and teaching-focused - teach, don't just summarize!

Generate comprehensive course content. Return ONLY valid JSON, no markdown formatting.
"""
        
        return prompt_intro
    
    def _create_simple_course(self, content: str, source_type: str, file_path: Optional[str]) -> Dict:
        """Create a simple course structure without AI (fallback)"""
        # Split content into chunks
        words = content.split()
        chunk_size = 500
        chunks = [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
        
        modules = []
        lesson_num = 1
        
        for i, chunk in enumerate(chunks[:5]):  # Max 5 modules
            lessons = []
            for j in range(min(3, len(chunks) - i * 3)):  # 3 lessons per module
                lesson_idx = i * 3 + j
                if lesson_idx < len(chunks):
                    lessons.append({
                        "title": f"Lesson {lesson_num}",
                        "order": j + 1,
                        "beginner_content": chunk[:500] + "...",
                        "intermediate_content": chunk[:1000] + "...",
                        "expert_content": chunk,
                        "examples": [],
                        "analogies": [],
                        "summary": chunk[:200] + "...",
                        "quizzes": [
                            {
                                "question": f"What is the main topic of this lesson?",
                                "options": ["Option A", "Option B", "Option C", "Option D"],
                                "correct_answer": 0,
                                "explanation": "Based on the content"
                            }
                        ],
                        "coding_tasks": []
                    })
                    lesson_num += 1
            
            if lessons:
                modules.append({
                    "title": f"Module {i + 1}",
                    "description": f"Module {i + 1} description",
                    "order": i + 1,
                    "lessons": lessons
                })
        
        toc = [
            {"module": m["order"], "title": m["title"], "lessons": [l["title"] for l in m["lessons"]]}
            for m in modules
        ]
        
        return {
            "title": f"Course from {source_type}",
            "description": f"Generated course from {source_type} content",
            "table_of_contents": toc,
            "modules": modules,
            "flashcards": [
                {"front": f"Question {i+1}", "back": f"Answer {i+1}"}
                for i in range(10)
            ]
        }
    
    def save_course_to_db(self, db: Session, course_data: Dict) -> Course:
        """Save generated course to database"""
        # Create course
        course = Course(
            title=course_data["title"],
            description=course_data.get("description", ""),
            source_type=course_data.get("source_type", "text"),
            table_of_contents=course_data.get("table_of_contents", [])
        )
        db.add(course)
        db.commit()
        db.refresh(course)
        
        # Create modules and lessons
        for module_data in course_data.get("modules", []):
            module = Module(
                course_id=course.id,
                title=module_data["title"],
                description=module_data.get("description", ""),
                order=module_data["order"]
            )
            db.add(module)
            db.commit()
            db.refresh(module)
            
            # Create lessons
            for lesson_data in module_data.get("lessons", []):
                lesson = Lesson(
                    module_id=module.id,
                    title=lesson_data["title"],
                    order=lesson_data["order"],
                    beginner_content=lesson_data.get("beginner_content", ""),
                    intermediate_content=lesson_data.get("intermediate_content", ""),
                    expert_content=lesson_data.get("expert_content", ""),
                    examples=lesson_data.get("examples", []),
                    analogies=lesson_data.get("analogies", []),
                    diagrams=lesson_data.get("diagrams", []),
                    summary=lesson_data.get("summary", ""),
                    coding_tasks=lesson_data.get("coding_tasks", [])
                )
                db.add(lesson)
                db.commit()
                db.refresh(lesson)
                
                # Create quizzes
                for quiz_data in lesson_data.get("quizzes", []):
                    quiz = Quiz(
                        lesson_id=lesson.id,
                        question=quiz_data["question"],
                        options=quiz_data["options"],
                        correct_answer=quiz_data["correct_answer"],
                        explanation=quiz_data.get("explanation", "")
                    )
                    db.add(quiz)
            
            db.commit()
        
        # Create flashcards
        for flashcard_data in course_data.get("flashcards", []):
            flashcard = Flashcard(
                course_id=course.id,
                front=flashcard_data["front"],
                back=flashcard_data["back"]
            )
            db.add(flashcard)
        
        db.commit()
        db.refresh(course)
        
        return course

