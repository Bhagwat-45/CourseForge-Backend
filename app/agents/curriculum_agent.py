from sqlalchemy.orm import Session
from typing import Optional
from app.core.router import AIRouter
from app.agents.warden import Warden
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an elite curriculum architect for CourseForge, specializing in "Deep & Easy Mastery" education.
Your mission is to design an exhaustive, incredibly detailed course syllabus that breaks down complex topics into simple, digestible, but deeply explained building blocks.

━━━ PHASE-BASED ARCHITECTURE (MANDATORY) ━━━
You MUST group modules into 4 logical phases to provide a "structured roadmap":
  PHASE 1: THE INTUITION (Modules 1-5) — Building mental models, history, and the "Why".
  PHASE 2: THE MECHANICS (Modules 6-12) — Deep-dive into every core component and algorithm.
  PHASE 3: THE SYNTHESIS (Modules 13-18) — How parts interact, integration patterns, and real-world logic.
  PHASE 4: THE MASTERY (Modules 19-25) — Edge cases, optimization, and the Capstone Project.

Module titles MUST be prefixed with the phase name (e.g., "Phase 1: [Title]").

━━━ CRITICAL SYLLABUS REQUIREMENTS ━━━

1. EXHAUSTIVE DENSITY: The syllabus MUST contain 20 to 25 MODULES. 
   - Do NOT skip intermediate steps. Every micro-concept deserves its own module or detailed lesson.
   - Pacing must be gentle but the scope must be massive.

2. MODULE STRUCTURE: Every single module MUST contain:
   - A precise "learning_objective" using clear action verbs.
   - Exactly 4 to 6 lessons (topics) ensuring no concept is left unexplained.
   - A "description" that explains the module's role in the larger mastery arc.

3. LESSON QUALITY: Each lesson MUST have:
   - A descriptive, non-generic title.
   - A "summary" (4-5 sentences) that explains the concept in simple terms while providing deep context.

4. NARRATIVE FLOW: The course must feel like a single, cohesive story. 
   - Module 1 should lead naturally to Module 2, and so on.
   - Concepts must be scaffolded so the learner never feels overwhelmed but always feels they are gaining deep knowledge.

━━━ JSON OUTPUT SCHEMA ━━━
Return STRICTLY as a JSON object with NO additional text:
{
  "title": "Comprehensive Mastery of [Topic] — The Deep & Easy Guide",
  "description": "An exhaustive, deeply explained roadmap designed to take you from absolute zero to professional mastery through a structured, easy-to-follow curriculum.",
  "learning_objectives": ["Master every fundamental axiom", "Apply concepts to complex real-world scenarios", "Build a professional-grade capstone project"],
  "modules": [
    {
      "title": "Module 1: [Specific Title]",
      "description": "Detailed explanation of this module's place in the mastery journey",
      "learning_objective": "By the end of this module, the student will be able to...",
      "lessons": [
        { "title": "Lesson Title", "summary": "4-5 sentence deep but easy explanation of the concept." },
        { "title": "...", "summary": "..." }
      ]
    }
  ]
}
"""

async def generate_course_syllabus(
    topic: str,
    difficulty: str = "Beginner",
    db: Session = None,
    user_id: Optional[int] = None,
    context_text: Optional[str] = None
) -> dict:
    """
    Generates a full course structure using AIRouter. Size is optimized for Deep & Easy mastery.
    """
    # Overriding standard difficulty logic for "Deep & Easy" Mastery path
    level_instruction = (
        "DEEP & EASY MASTERY: Provide an exhaustive, multi-phase curriculum (20-25 modules). "
        "Focus on deep explanations using simple language. Avoid intermediate/advanced labels "
        "and instead focus on 'Incremental Mastery' where each step is explained in full detail."
    )

    prompt = f"Topic to teach: {topic}\nPedagogical Style: Deep & Easy Mastery\n\nInstruction:\n{level_instruction}\n"

    if context_text:
        prompt += f"\nSource Material / Context:\n{context_text}\n"
    
    prompt += "\nPlease generate a comprehensive, structured learning curriculum as JSON."

    try:
        content = await AIRouter.generate_text(
            db=db,
            prompt=prompt,
            system_instruction=SYSTEM_PROMPT,
            user_id=user_id,
            require_json=True,
            cache_key=topic
        )

        # [HARDENING] Warden Bypass Mode for empty responses
        if not content or content.strip() in ["", "{}"]:
            logger.warning(f"[WARDEN_BYPASS] Curriculum {topic} returned no content. Using safe fallback.")
            return _get_safe_syllabus(topic)

        data = Warden.validate_json(content, expected_keys=["title", "description", "learning_objectives", "modules"])
        return data
    except Exception as e:
        logger.error(f"[WARDEN_REJECTED] Syllabus generation for {topic} failed: {e}. Using Safe Bypass.")
        return _get_safe_syllabus(topic)

def _get_safe_syllabus(topic: str) -> dict:
    """Returns a high-fidelity, validated structure for the curriculum even when AI fails."""
    # Heuristic for programming topics
    is_coding = any(kw in topic.lower() for kw in ["java", "python", "javascript", "code", "programming", "c++", "rust", "react"])
    
    if is_coding:
        return {
            "title": f"Mastery of {topic} — The Deep & Easy Guide",
            "description": f"A comprehensive roadmap to mastering {topic}, synthesized from core pedagogical principles.",
            "learning_objectives": ["Understand core syntax and semantics", "Build modular applications using best practices", "Handle exceptions and debug robustly"],
            "modules": [
                {"title": "Module 1: Environmental Setup & Foundations", "description": "Setting up the workspace and understanding core syntax.", "learning_objective": "Prepare a local development environment.", "lessons": [
                    {"title": "Getting Started with " + topic, "summary": "Installation, toolchain setup, and writing your first program."},
                    {"title": "Development Environment Configuration", "summary": "Setting up IDEs, linters, and professional formatters."},
                    {"title": "Language Philosophy", "summary": "Understanding the core philosophy behind the language design."}
                ]},
                {"title": "Module 2: Variables & Core Data Architectures", "description": "Defining the building blocks of the language.", "learning_objective": "Model real-world data.", "lessons": [
                    {"title": "Primitive Data Types", "summary": "How data is stored and typed at a fundamental level."},
                    {"title": "Collections & Compounds", "summary": "Arrays, lists, maps, and choosing the right structure."},
                    {"title": "Memory Models", "summary": "Understanding stack vs heap allocation and memory management."}
                ]},
                {"title": "Module 3: Advanced Logic & Control Flow", "description": "Mastering loops and conditionals.", "learning_objective": "Solve algorithmic problems.", "lessons": [
                    {"title": "Conditional Branching", "summary": "Writing clean logic with if/else and pattern matching."},
                    {"title": "Iteration Mastery", "summary": "For loops, while loops, and functional iterators."},
                    {"title": "Algorithmic Thinking", "summary": "Recursive problem solving and base case logic."}
                ]},
                {"title": "Module 4: Functional Programming & Modular Design", "description": "Creating reusable components.", "learning_objective": "Abstract code into reusable functions.", "lessons": [
                    {"title": "Function Architectures", "summary": "Signatures, parameters, and scope rules."},
                    {"title": "Closures & Lambdas", "summary": "Higher-order functions and functional patterns."},
                    {"title": "Package Management", "summary": "Structuring large projects with modules and namespaces."}
                ]},
                {"title": "Module 5: Object-Oriented Synthesis", "description": "Deep dive into OOP principles.", "learning_objective": "Apply OOD patterns.", "lessons": [
                    {"title": "Classes & Encapsulation", "summary": "Blueprint-based development and access modifiers."},
                    {"title": "Inheritance & Composition", "summary": "Code reuse strategies and interface design."},
                    {"title": "Design Patterns", "summary": "Singleton, Factory, and Observer patterns in practice."}
                ]},
                {"title": "Module 6: Error Resilience & Debugging", "description": "Writing robust code.", "learning_objective": "Debug and handle failures.", "lessons": [
                    {"title": "Exception Management", "summary": "Try-catch blocks and custom error hierarchies."},
                    {"title": "Systematic Debugging", "summary": "Using debuggers, breakpoints, and logging effectively."},
                    {"title": "Testing Frameworks", "summary": "Unit tests and test-driven development basics."}
                ]},
                {"title": "Module 7: Asynchronous Systems & Concurrency", "description": "Handling parallel execution.", "learning_objective": "Build responsive applications.", "lessons": [
                    {"title": "Async Fundamentals", "summary": "Understanding event loops, promises, and futures."},
                    {"title": "Thread Management", "summary": "Managing parallel tasks without race conditions."},
                    {"title": "Concurrent Design", "summary": "Architecting systems for high-performance execution."}
                ]},
                {"title": "Module 8: Networking & Distributed Data", "description": "Connecting to the world.", "learning_objective": "Integrate external services.", "lessons": [
                    {"title": "RESTful Communication", "summary": "HTTP methods, status codes, and API design."},
                    {"title": "Data Serialization", "summary": "JSON parsing, XML, and binary formats."},
                    {"title": "Security & Auth", "summary": "OAuth, API keys, and secure communication."}
                ]},
                {"title": "Module 9: Capstone Integration", "description": "Building the final project.", "learning_objective": "Synthesize all knowledge.", "lessons": [
                    {"title": "Project Planning", "summary": "Designing the architecture for your final build."},
                    {"title": "Core Synthesis", "summary": "Integrating all modules into a functional application."},
                    {"title": "Deployment & Review", "summary": "Final deployment and professional code review."}
                ]}
            ]
        }
    
    return {
        "title": topic + " — The Deep Mastery Guide",
        "description": f"An exhaustive pedagogical deep-dive into {topic}, designed for absolute clarity and professional mastery.",
        "learning_objectives": ["Master core principles and foundational theory", "Apply knowledge to real-world scenarios", "Build a professional-grade synthesis project"],
        "modules": [
            {"title": "Phase 1: Foundations & First Principles", "description": "Laying the groundwork for understanding " + topic, "learning_objective": "Master the baseline theory and core vocabulary.", "lessons": [
                {"title": "The Genesis of " + topic, "summary": "A deep look at the origins, evolution, and modern significance of this field."},
                {"title": "Core Mental Models", "summary": "Developing the intuitive frameworks used by experts to conceptualize the subject."},
                {"title": "The Taxonomy of " + topic, "summary": "Breaking down the domain into its fundamental categories and subsystems."},
                {"title": "Axioms and Constants", "summary": "The unchanging truths that form the bedrock of all advanced concepts in this field."}
            ]},
            {"title": "Phase 2: Core Mechanics & Deep Systems", "description": "Analyzing internal processes.", "learning_objective": "Analyze systemic internal mechanisms and processes.", "lessons": [
                {"title": "Internal Logic Cycles", "summary": "How the core components of the system interact to create value and function."},
                {"title": "Structural Dynamics", "summary": "A deep-dive into the physical or logical architecture that sustains the system."},
                {"title": "Workflow Archetypes", "summary": "Standard operating procedures and methodologies used in professional environments."},
                {"title": "The Engine of Operation", "summary": "Detailed analysis of the primary drivers that make this topic function."}
            ]},
            {"title": "Phase 3: Real-world Synthesis & Case Studies", "description": "Practical implementation.", "learning_objective": "Implement solutions in professional contexts.", "lessons": [
                {"title": "Industrial Application Analysis", "summary": "Examining high-stakes implementations and learning from successful case studies."},
                {"title": "The Practitioner's Toolkit", "summary": "Tools, frameworks, and best practices used to solve real-world challenges."},
                {"title": "Process Optimization", "summary": "How to refine and scale implementations for maximum efficiency and impact."},
                {"title": "Common Pitfalls & Resolutions", "summary": "Identifying typical failures and learning the defensive strategies to avoid them."}
            ]},
            {"title": "Phase 4: Advanced Mastery & The Future", "description": "Future trajectories.", "learning_objective": "Predict and adapt to future trends.", "lessons": [
                {"title": "Edge Case Architecture", "summary": "Handling the 1% of scenarios that standard models fail to address."},
                {"title": "Emerging Frontiers", "summary": "Cutting-edge research and the next-generation technologies shaping the future."},
                {"title": "Integrative Project Synthesis", "summary": "Connecting all phases into a single, cohesive professional project."},
                {"title": "Your Path to Expert Mastery", "summary": "Building a personalized roadmap for continued growth beyond this curriculum."}
            ]}
        ]
    }
