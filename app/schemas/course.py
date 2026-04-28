from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

class QuizSchema(BaseModel):
    question: str
    options: List[str]
    correct_answer: int
    explanation: str
    wrong_option_explanations: Optional[List[str]] = None
    difficulty: str
    bloom_level: Optional[str] = None
    concept_node: Optional[str] = None


    class Config:
        from_attributes = True

class TopicSchema(BaseModel):
    id: int
    order: int
    title: str
    beginner_content: Optional[str] = ""
    intermediate_content: Optional[str] = ""
    expert_content: Optional[str] = ""
    examples: Optional[List[str]] = []
    code: Optional[List[str]] = []
    takeaways: Optional[List[str]] = []
    analogies: Optional[List[str]] = []
    technical_terms: Optional[List[str]] = []
    summary: Optional[str] = ""
    generation_status: Optional[str] = "ready"
    youtube_params: Optional[Dict] = None
    diagrams: Optional[List[Dict]] = None
    last_error: Optional[str] = None
    last_generated_at: Optional[datetime] = None
    quizzes: List[QuizSchema] = []
    
    # Deep pedagogical content fields (v2)
    learning_objectives: Optional[List[str]] = []
    concept_explanation: Optional[str] = ""
    subtopics: Optional[List[Dict]] = []
    worked_examples: Optional[List[Dict]] = []
    misconceptions: Optional[List[Dict]] = []
    practical_applications: Optional[List[str]] = []
    practice_exercises: Optional[List[Dict]] = []
    video_resources: Optional[List[Dict]] = []
    code_examples: Optional[List[Dict]] = []
    key_takeaways: Optional[List[str]] = []

    class Config:
        from_attributes = True

class ModuleSchema(BaseModel):
    id: Optional[int] = None
    order: int
    title: str
    description: str
    topics: List[TopicSchema]

    class Config:
        from_attributes = True

class CourseGenerateRequest(BaseModel):
    topic: str
    difficulty: Optional[str] = "starter"  # starter, intermediate, advanced

class CourseBase(BaseModel):
    title: str
    description: str
    difficulty: str
    source_type: str = "text"

class CourseCreate(CourseBase):
    pass

class CourseResponse(CourseBase):
    id: int
    status: str
    created_at: datetime
    modules: List[ModuleSchema] = []

    class Config:
        from_attributes = True

class ProgressUpdate(BaseModel):
    completed_topic_ids: List[int]
    quiz_scores: Dict[int, int]
    overall_percentage: float

class ProgressResponse(ProgressUpdate):
    id: int
    user_id: int
    course_id: int
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
