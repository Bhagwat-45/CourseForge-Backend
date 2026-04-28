import json
from app.core.llm import invoke_with_retry
from app.agents.warden import Warden

SYSTEM_PROMPT = """You are the 'CourseForge Lab Warden'. Your job is to create and evaluate practical 'Hands-on Labs' for students.

1. When asked to CREATE a lab:
   Return a JSON object with: 
   { 
     "exercise": "Detailed task description", 
     "requirements": ["List of checkable requirements"], 
     "hints": ["Helpful nudges"],
     "language": "python or javascript",
     "initial_code": "Optional boilerplate code for the student"
   }

2. When asked to EVALUATE a lab:
   Analyze the user's submission against the exercise.
   Return a JSON object with: 
   { 
     "passed": boolean, 
     "feedback": "Constructive pedagogical feedback", 
     "score": number (0-100), 
     "xp_awarded": 150 
   }
   Be strict but fair. Reward creativity and clean code.
"""

def create_lab_exercise(topic_title: str, topic_content: str) -> dict:
    content = invoke_with_retry(
        prompt=f"CREATE a hands-on lab exercise for:\nTitle: {topic_title}\nContent: {topic_content}",
        system_instruction=SYSTEM_PROMPT
    )
    
    try:
        return Warden.validate_json(content, expected_keys=["exercise", "requirements", "hints", "language"])
    except:
        return {
            "exercise": "Explain the core concepts of this topic in your own words.", 
            "requirements": ["Clarity", "Accuracy"], 
            "hints": ["Think about real-world use cases."],
            "language": "python",
            "initial_code": "# Start your exploration here\n"
        }

def evaluate_lab_submission(exercise: dict, submission: str) -> dict:
    content = invoke_with_retry(
        prompt=f"EVALUATE this lab submission.\nExercise: {json.dumps(exercise)}\nSubmission: {submission}",
        system_instruction=SYSTEM_PROMPT
    )
    
    try:
        return Warden.validate_json(content, expected_keys=["passed", "feedback", "score", "xp_awarded"])
    except Exception as e:
        return {"passed": False, "feedback": "System encountered an anomaly while evaluating. Please re-submit your code.", "score": 0, "xp_awarded": 0}
