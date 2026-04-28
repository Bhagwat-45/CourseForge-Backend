from sqlalchemy.orm import Session
from typing import Optional
from app.core.router import AIRouter
from app.agents.warden import Warden
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an elite educational content architect for CourseForge.
Your mission is to produce *publication-quality*, long-form pedagogical content that transforms passive readers into active practitioners.
Every chapter you produce must feel like a **mini interactive textbook chapter** — not a short AI summary.

━━━ PEDAGOGICAL FRAMEWORK (Bloom's Taxonomy + UDL) ━━━
Structure every lesson to move the learner through cognitive levels:
  Remember → Understand → Apply → Analyze → Evaluate → Create

Use Universal Design for Learning (UDL):
  - Multiple means of Representation (text, diagrams, analogies, code)
  - Multiple means of Engagement (exercises, quizzes, real-world applications)
  - Multiple means of Expression (worked examples, practice problems)

━━━ CONTENT DENSITY REQUIREMENTS ━━━
CRITICAL: You must generate DEEP, THOROUGH content — not surface-level summaries.
  - concept_explanation: MINIMUM 2000 words. Multiple paragraphs, richly detailed.
  - Each subtopic: MINIMUM 400 words with real depth.
  - Worked examples: Must show full problem → solution → explanation chain.
  - Code examples: Must be production-quality with extensive inline comments.

━━━ LAYERED DIFFICULTY (Beginner → Intermediate → Expert) ━━━
The concept_explanation field must use layered depth:
  1. START with simple, intuitive explanations a complete beginner can grasp
  2. THEN build toward intermediate complexity with more technical detail
  3. THEN push into advanced territory with edge cases, trade-offs, and expert insights
  
Mark these transitions with Markdown headers:
  ### 🟢 Foundation (Beginner)
  ### 🟡 Going Deeper (Intermediate)  
  ### 🔴 Expert Territory (Advanced)

━━━ JSON PAYLOAD REQUIREMENTS ━━━
Return ONLY a valid JSON object with this EXACT schema — no additional text:
{
  "title": "Topic Title",
  
  "learning_objectives": [
    "After this lesson, you will be able to [ACTION VERB] ...",
    "You will understand how [CONCEPT] relates to ...",
    "You will be able to implement [SKILL] in ..."
  ],
  
  "concept_explanation": "## Deep Explanation (2000+ words)\\n\\nMultiple rich paragraphs using Markdown...\\n\\n### 🟢 Foundation\\n...\\n### 🟡 Going Deeper\\n...\\n### 🔴 Expert Territory\\n...",
  
  "subtopics": [
    {
      "title": "Subtopic Title",
      "content": "Detailed explanation with multiple paragraphs, bullet points, and technical depth (400+ words)..."
    }
  ],
  
  "analogies": [
    "A vivid, relatable analogy that anchors the abstract concept to something concrete. E.g., 'A hash map is like a library card catalog — you look up the card (key) to find exactly which shelf (memory address) holds your book (value).'",
    "Another analogy from a different angle..."
  ],
  
  "worked_examples": [
    {
      "title": "Descriptive Example Title",
      "problem": "Clear problem statement that the student must solve",
      "solution": "Step-by-step solution with full working shown",
      "explanation": "Why this solution works, what principles it demonstrates, and common mistakes to avoid"
    }
  ],
  
  "diagrams": [
    {
      "title": "Descriptive Diagram Title",
      "code": "graph TD\\n    A[Start] -->|step 1| B[Process]\\n    B -->|validates| C{Decision}\\n    C -->|yes| D[Success]\\n    C -->|no| E[Retry]"
    }
  ],
  
  "code_examples": [
    {
      "title": "Example Title",
      "language": "python",
      "code": "# Full, production-quality code with inline comments\\ndef example():\\n    pass",
      "explanation": "Line-by-line explanation of what this code does and why each design choice was made"
    }
  ],
  
  "misconceptions": [
    {
      "myth": "Common misconception students have",
      "reality": "The actual truth",
      "why": "Why students make this mistake and how to avoid it"
    }
  ],
  
  "practical_applications": [
    "Real-world application 1 with specific industry context",
    "Real-world application 2 with specific use case"
  ],
  
  "practice_exercises": [
    {
      "question": "A practice problem that tests understanding (not multiple choice)",
      "hint": "A helpful hint to guide the student",
      "answer": "The complete answer with explanation"
    }
  ],
  
  "quizzes": [
    {
      "question": "Clear, pedagogically sound question text?",
      "options": ["Correct Option", "Distractor A", "Distractor B", "Distractor C"],
      "correct_answer": 0,
      "explanation": "Deep explanation of the correct concept.",
      "wrong_option_explanations": [
        "Why Distractor A is incorrect (e.g., 'This is a common confusion with [Concept X]')",
        "Why Distractor B is incorrect...",
        "Why Distractor C is incorrect..."
      ],
      "difficulty": "Beginner",
      "bloom_level": "Recall",
      "concept_node": "Topic Title"
    }
  ],
  
  "flashcards": [
    {"front": "Key Term 1", "back": "Precise, memorable definition"},
    {"front": "Key Term 2", "back": "Precise, memorable definition"},
    {"front": "Key Term 3", "back": "Precise, memorable definition"},
    {"front": "Key Concept 4", "back": "Precise, memorable explanation"},
    {"front": "Key Concept 5", "back": "Precise, memorable explanation"}
  ],
  
  "key_takeaways": [
    "Critical insight 1 — the ONE thing the student must remember",
    "Critical insight 2 — connecting this topic to broader concepts",
    "Critical insight 3 — practical wisdom for real-world application"
  ],
  
  "summary": "A synthesized 3-5 sentence conclusion that ties the lesson back to the course narrative and previews what comes next",
  
  "video_resources": [
    {
      "query": "Highly specific YouTube search query for THIS exact topic (e.g., 'Binary Search Algorithm Visual Explanation Step by Step')",
      "relevance": "Why this video is specifically relevant to what was taught in THIS lesson",
      "focus_area": "Specific parts of the video to focus on (e.g., 'Watch the visual walkthrough at 2:30-5:00')"
    },
    {
      "query": "Another targeted search query for a different aspect of the topic",
      "relevance": "Why this complements the lesson content",
      "focus_area": "Specific focus area"
    }
  ],
  
  "technical_terms": ["Term 1", "Term 2", "Term 3", "Term 4", "Term 5"],
  
  "beginner_content": "Copy of the 🟢 Foundation section from concept_explanation...",
  "intermediate_content": "Copy of the 🟡 Going Deeper section from concept_explanation...",
  "expert_content": "Copy of the 🔴 Expert Territory section from concept_explanation...",
  "examples": ["Summary of worked example 1", "Summary of worked example 2"],
  "code": ["Code snippet 1 from code_examples", "Code snippet 2"],
  "takeaways": ["Takeaway 1", "Takeaway 2", "Takeaway 3"]
}

━━━ QUALITY GATES ━━━
- NEVER return fewer than 3 learning_objectives.
- concept_explanation MUST be 2000+ words with all three difficulty tiers.
- NEVER return fewer than 2 subtopics, each 400+ words.
- NEVER return fewer than 2 worked_examples with full problem/solution/explanation.
- NEVER return fewer than 2 diagrams (use Mermaid syntax: flowchart, sequenceDiagram, classDiagram, etc.).
- NEVER return fewer than 2 misconceptions.
- NEVER return fewer than 5 quizzes. You MUST generate exactly five questions. One for each of these specific pedagogical categories:
    1. Foundational Recall: Testing basic facts/definitions from the lesson. (Bloom: Remember)
    2. Conceptual Understanding: Testing the 'why' and 'how' behind the concepts. (Bloom: Understand)
    3. Applied Scenario: A real-world problem where the student must apply the concept. (Bloom: Apply)
    4. Misconception Trap: Specifically targeting one of the myths/misconceptions listed in the lesson. (Bloom: Analyze)
    5. Higher-Order Reasoning: Complex evaluation or synthesis of multiple subtopics. (Bloom: Evaluate)

- For EVERY quiz question, you MUST provide:
    - question: Clear, challenging text.
    - options: Exactly 4 distinct options.
    - correct_answer: Index (0-3).
    - explanation: Why the correct answer is correct.
    - wrong_option_explanations: Exactly 3 explanations for why the distractors are wrong.
    - difficulty: "Beginner", "Intermediate", or "Advanced".
    - bloom_level: One of the 5 levels mentioned above.
    - concept_node: The specific subtopic or concept this question tests.

- EXACTLY 5 QUIZZES. NO EXCEPTIONS.
- ALL questions must be derived directly from the content you generated (objectives, explanation, subtopics, examples, misconceptions).
- NEVER use generic questions. Each must be unique to this topic.
"""

async def generate_topic_content(
    course_title: str, 
    module_title: str, 
    topic_title: str, 
    level: str = "Beginner", 
    context_text: str = "",
    db: Session = None,
    user_id: Optional[int] = None
) -> dict:
    """Generates rich, deeply explained structured content for a topic chapter."""
    prompt = f"""Course: {course_title}
Module: {module_title}
Topic: {topic_title}
Style: Deep Pedagogical Mastery — write as if authoring an interactive textbook chapter.

IMPORTANT: Generate content that is THOROUGH and DETAILED. This is not a summary — it is a complete lesson.
- The concept_explanation must be at minimum 2000 words with layered difficulty (beginner → intermediate → expert).
- Every worked_example must show the full problem, step-by-step solution, and explanation.
- Code examples must be production-quality with extensive comments.
- Diagrams must use valid Mermaid syntax.
- Video search queries must be SPECIFIC to this exact topic (not generic).
"""
    
    if context_text:
        prompt += f"\nAdditional Context: {context_text}\n"
        
    try:
        content = await AIRouter.generate_text(
            db=db,
            prompt=prompt,
            system_instruction=SYSTEM_PROMPT,
            user_id=user_id,
            require_json=True,
            cache_key=f"topic_v2_{topic_title}_{level}"
        )
        
        if not content or content.strip() in ["", "{}"]:
            return _get_safe_topic_data(topic_title)

        data = Warden.validate_json(content, expected_keys=[
            "title", "concept_explanation", "beginner_content", "intermediate_content", "expert_content", 
            "examples", "code", "takeaways", "quizzes", "flashcards", "summary"
        ])
        
        result = {
            "title": data["title"],
            "technical_terms": data.get("technical_terms", []),
            
            # New deep pedagogical fields
            "learning_objectives": data.get("learning_objectives", []),
            "concept_explanation": data.get("concept_explanation", ""),
            "subtopics": data.get("subtopics", []),
            "worked_examples": data.get("worked_examples", []),
            "misconceptions": data.get("misconceptions", []),
            "practical_applications": data.get("practical_applications", []),
            "practice_exercises": data.get("practice_exercises", []),
            "video_resources": data.get("video_resources", []),
            "code_examples": data.get("code_examples", []),
            # Standard fields
            "flashcards": data["flashcards"],
            "summary": data["summary"],
            "diagrams": data.get("diagrams", []),
            "quizzes": data.get("quizzes", [])[:5], # Ensure max 5
        }
        
        # Ensure exactly 5 quizzes by padding with safe ones if needed
        if len(result["quizzes"]) < 5:
            safe_quizzes = _get_safe_topic_data(topic_title)["quizzes"]
            while len(result["quizzes"]) < 5:
                result["quizzes"].append(safe_quizzes[len(result["quizzes"])])
        
        return result
    except Exception as e:
        logger.error(f"[AI_ERROR] {e}")
        return _get_safe_topic_data(topic_title)

def _get_safe_topic_data(topic_title: str) -> dict:
    """Returns a rich, professional placeholder structure when AI fails."""
    topic_lc = topic_title.lower()
    is_coding = any(kw in topic_lc for kw in ["java", "python", "javascript", "code", "programming", "variable", "function", "class", "object", "c++", "react", "rust", "go", "sql"])
    
    concept_explanation = f"""## Understanding {topic_title}

### 🟢 Foundation (Beginner)

{topic_title} is a fundamental concept that forms the backbone of this curriculum. At its core, it provides the logical structure needed to understand more complex ideas that build upon it.

Think of it like learning the alphabet before writing sentences — {topic_title} gives you the foundational building blocks that everything else depends on.

### 🟡 Going Deeper (Intermediate)

As you develop a stronger grasp of {topic_title}, you'll begin to see how it connects to other concepts in the field. The relationships between these ideas form a web of knowledge that enables practical problem-solving.

### 🔴 Expert Territory (Advanced)

At the expert level, understanding {topic_title} means recognizing its edge cases, trade-offs, and the design decisions behind its implementation. This section will be populated with advanced AI-synthesized content once the neural grid stabilizes.

*Note: This content is running in Neural Cache mode. Deep AI synthesis will resume shortly.*"""

    if is_coding:
        code_examples = [{
            "title": f"Basic {topic_title} Implementation",
            "language": "python" if "python" in topic_lc else "java" if "java" in topic_lc else "javascript",
            "code": f"# Standard implementation pattern for {topic_title}\n# Neural Grid synthesis placeholder\nprint('CourseForge Active')",
            "explanation": f"This demonstrates the basic structure used when implementing {topic_title}."
        }]
    else:
        code_examples = []

    return {
        "title": topic_title,
        "technical_terms": [topic_title, "Mastery", "Principles", "Implementation", "Architecture"],
        
        "learning_objectives": [
            f"Understand the fundamental principles of {topic_title}",
            f"Apply {topic_title} concepts to solve real-world problems",
            f"Analyze and evaluate different approaches to {topic_title}"
        ],
        "concept_explanation": concept_explanation,
        "subtopics": [
            {"title": f"Core Principles of {topic_title}", "content": f"The foundational principles that underpin {topic_title} and how they relate to the broader curriculum."},
            {"title": f"Practical Applications", "content": f"How {topic_title} is applied in real-world scenarios across various industries and domains."}
        ],
        "worked_examples": [
            {
                "title": f"Applying {topic_title} in Practice",
                "problem": f"Given a scenario involving {topic_title}, determine the optimal approach.",
                "solution": "This worked example will be populated with AI-synthesized content.",
                "explanation": f"This demonstrates how {topic_title} principles translate to practical problem-solving."
            }
        ],
        "misconceptions": [
            {
                "myth": f"{topic_title} is too complex for beginners",
                "reality": "With the right foundation and analogies, anyone can grasp the core concepts",
                "why": "Many learners feel intimidated by new terminology, but the underlying ideas are often quite intuitive"
            }
        ],
        "practical_applications": [
            f"Real-world application of {topic_title} in professional settings",
            f"How {topic_title} influences modern industry practices"
        ],
        "practice_exercises": [
            {
                "question": f"Explain in your own words why {topic_title} matters in this field",
                "hint": "Think about what problems it solves and what would happen without it",
                "answer": f"{topic_title} provides essential structure and logic for the domain"
            }
        ],
        "video_resources": [
            {
                "query": f"{topic_title} explained simply for beginners",
                "relevance": f"Provides visual and auditory reinforcement of the {topic_title} concepts covered in this lesson",
                "focus_area": "Watch the introduction and core concept sections"
            }
        ],
        "code_examples": code_examples,
        
        "beginner_content": concept_explanation,
        "intermediate_content": concept_explanation + "\n\n*Note: Neural Cache mode active.*",
        "expert_content": concept_explanation + "\n\n**Advanced synthesis pending grid stabilization.**",
        "examples": [f"Practical application of {topic_title} in production.", "How this concept integrates with other systems."],
        "code": [c["code"] for c in code_examples] if code_examples else [],
        "takeaways": [f"Understanding the first principles of {topic_title}.", f"How to apply {topic_title} to solve real challenges."],
        "key_takeaways": [f"Understanding the first principles of {topic_title}.", f"How to apply {topic_title} to solve real challenges."],
        "analogies": [f"Think of {topic_title} as a fundamental building block in a much larger machine."],
        "summary": f"A baseline synthesis of {topic_title} for immediate study. Deep AI content will be generated on next request.",
        "diagrams": [],
        "quizzes": [
            {
                "question": f"What is the primary objective of {topic_title}?",
                "options": ["To provide logical structure", "To confuse the system", "To increase latency", "To skip validation"],
                "correct_answer": 0,
                "explanation": f"{topic_title} is designed to provide a stable logical structure to the system.",
                "wrong_option_explanations": ["This would degrade the product.", "Performance is a secondary goal to correctness.", "Safety first."],
                "difficulty": "Beginner",
                "bloom_level": "Recall",
                "concept_node": topic_title
            },
            {
                "question": f"How does {topic_title} contribute to the overall course architecture?",
                "options": ["By acting as an isolated component", "By providing a foundational layer", "By replacing all other modules", "By reducing content density"],
                "correct_answer": 1,
                "explanation": f"{topic_title} acts as a foundation for more advanced modules.",
                "wrong_option_explanations": ["Components are integrated.", "It's a building block, not a total replacement.", "We aim for high density."],
                "difficulty": "Intermediate",
                "bloom_level": "Understand",
                "concept_node": topic_title
            },
            {
                "question": f"In a real-world scenario, why would an expert prioritize {topic_title}?",
                "options": ["To save development time", "To ensure long-term scalability and reliability", "To follow a trend", "To increase complexity"],
                "correct_answer": 1,
                "explanation": "Expert practitioners focus on the long-term robustness of their implementations.",
                "wrong_option_explanations": ["Quality takes time.", "Trends are fleeting.", "Simplicity is preferred."],
                "difficulty": "Advanced",
                "bloom_level": "Apply",
                "concept_node": topic_title
            },
            {
                "question": f"Which of these is a common misconception about {topic_title}?",
                "options": ["It is only useful for large projects", "It requires expensive infrastructure", "It is too complex for fast-paced environments", "All of the above"],
                "correct_answer": 3,
                "explanation": f"{topic_title} is actually versatile and applicable across various scales and budgets.",
                "wrong_option_explanations": ["Useful for all sizes.", "Runs on standard hardware.", "Speeds up long-term development."],
                "difficulty": "Intermediate",
                "bloom_level": "Analyze",
                "concept_node": topic_title
            },
            {
                "question": f"How should {topic_title} be evaluated in the context of professional mastery?",
                "options": ["By how quickly it can be implemented", "By its ability to solve complex edge cases reliably", "By the number of lines of code it uses", "By its popularity"],
                "correct_answer": 1,
                "explanation": "Mastery is demonstrated through handling complex, non-trivial scenarios.",
                "wrong_option_explanations": ["Speed != Mastery.", "Succinctness is usually better.", "Popularity != Quality."],
                "difficulty": "Advanced",
                "bloom_level": "Evaluate",
                "concept_node": topic_title
            }
        ],
        "flashcards": [
            {"front": f"What does {topic_title} represent?", "back": "A fundamental concept in the curriculum."},
            {"front": f"Why is {topic_title} important?", "back": "It provides foundational structure for more advanced topics."}
        ]
    }

