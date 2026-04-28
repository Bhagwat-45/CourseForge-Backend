from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey, Text, JSON, Float, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class DifficultyLevel(str, enum.Enum):
    STARTER = "starter"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    name = Column(String)
    age = Column(Integer, nullable=True)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    badges = Column(JSON, default=list) # List of strings: ["python_starter", "speed_learner"]
    streak_days = Column(Integer, default=0)
    last_active_date = Column(Date, nullable=True)
    
    # --- Usage Tracking ---
    generation_count = Column(Integer, default=0)
    cycle_start_date = Column(DateTime(timezone=True), server_default=func.now())
    cycle_end_date = Column(DateTime(timezone=True), server_default=func.now()) # Will be updated dynamically
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    courses = relationship("Course", back_populates="owner")
    progress = relationship("CourseProgress", back_populates="user")
    flashcard_reviews = relationship("FlashcardReview", back_populates="user")
    discussions = relationship("Discussion", back_populates="user")

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text, nullable=True)
    source_type = Column(String, default="text")  # text, pdf, image
    status = Column(String, default="ready")      # planning, generating, ready
    difficulty = Column(Enum(DifficultyLevel), default=DifficultyLevel.STARTER)
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    # --- SaaS Features ---
    content_json = Column(JSON, nullable=True)
    pdf_url = Column(String, nullable=True)
    knowledge_graph = Column(JSON, nullable=True) # Pre-calculated DAG representation
    
    last_generated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="courses")
    modules = relationship("Module", back_populates="course", cascade="all, delete-orphan")
    flashcards = relationship("Flashcard", back_populates="course", cascade="all, delete-orphan")
    progress_entries = relationship("CourseProgress", back_populates="course", cascade="all, delete-orphan")

class Module(Base):
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    order = Column(Integer, default=0)
    title = Column(String)
    description = Column(Text, nullable=True)

    course = relationship("Course", back_populates="modules")
    topics = relationship("Topic", back_populates="module", cascade="all, delete-orphan")

class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("modules.id"))
    order = Column(Integer, default=0)
    title = Column(String)
    generation_status = Column(String, default="ready") # pending, generating, ready, failed
    
    # Three levels of explanation
    beginner_content = Column(Text)
    intermediate_content = Column(Text)
    expert_content = Column(Text)
    
    examples = Column(JSON)  # List of strings
    code = Column(JSON)      # List of strings
    takeaways = Column(JSON) # List of strings
    analogies = Column(JSON) # List of strings
    technical_terms = Column(JSON, nullable=True) # List of key terms for highlighting
    summary = Column(Text)
    
    # Deep pedagogical content fields (v2)
    prerequisite_topic_ids = Column(JSON, default=list)  # Deterministic graph links
    vector_doc_ids = Column(JSON, nullable=True)         # ChromaDB reference links
    learning_objectives = Column(JSON, nullable=True)    # List of objective strings
    concept_explanation = Column(Text, nullable=True)     # Long-form layered explanation
    subtopics = Column(JSON, nullable=True)               # [{title, content}]
    worked_examples = Column(JSON, nullable=True)         # [{title, problem, solution, explanation}]
    misconceptions = Column(JSON, nullable=True)          # [{myth, reality, why}]
    practical_applications = Column(JSON, nullable=True)  # List of application strings
    practice_exercises = Column(JSON, nullable=True)      # [{question, hint, answer}]
    video_resources = Column(JSON, nullable=True)         # [{query, relevance, focus_area}]
    code_examples = Column(JSON, nullable=True)           # [{title, language, code, explanation}]
    key_takeaways = Column(JSON, nullable=True)           # List of takeaway strings
    
    # Visuals & Media
    youtube_params = Column(JSON, nullable=True) # {title, channel, search_url, search_query}
    images = Column(JSON, nullable=True)         # [{"alt": "...", "url": "..."}]
    diagrams = Column(JSON, nullable=True)       # [{"title": "...", "code": "graph TD..."}]
    
    # Adaptive Mastery (v5)
    mastery_score = Column(Float, default=0.0)
    struggle_count = Column(Integer, default=0)
    
    last_error = Column(Text, nullable=True)     # Store last generation error message
    last_generated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    module = relationship("Module", back_populates="topics")
    quizzes = relationship("Quiz", back_populates="topic", cascade="all, delete-orphan")

class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"))
    question = Column(Text)
    options = Column(JSON)      # List of strings
    correct_answer = Column(Integer) # Index
    explanation = Column(Text)
    wrong_option_explanations = Column(JSON, nullable=True) # List of explanations for wrong options
    difficulty = Column(String) # easy, medium, hard
    bloom_level = Column(String, nullable=True) # Recall, Understand, Apply, Analyze, Evaluate, Create
    concept_node = Column(String, nullable=True) # Linked concept/topic node for mastery tracking


    topic = relationship("Topic", back_populates="quizzes")

class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    front = Column(Text)
    back = Column(Text)

    course = relationship("Course", back_populates="flashcards")
    reviews = relationship("FlashcardReview", back_populates="flashcard", cascade="all, delete-orphan")

class CourseProgress(Base):
    __tablename__ = "course_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    completed_topic_ids = Column(JSON, default=list) # List of integer topic IDs
    last_topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)
    quiz_scores = Column(JSON, default=dict)         # {topic_id: score}
    overall_percentage = Column(Float, default=0.0)
    
    # Adaptive Mastery (v5)
    mastery_heatmap = Column(JSON, default=dict)     # Node_id -> Mastery Float
    learning_velocity = Column(Float, default=1.0)   # Moving average of time-to-completion vs average
    
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="progress")
    course = relationship("Course", back_populates="progress_entries")



class FlashcardReview(Base):
    __tablename__ = "flashcard_reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    flashcard_id = Column(Integer, ForeignKey("flashcards.id"))
    ease_factor = Column(Float, default=2.5)
    interval_days = Column(Integer, default=1)
    repetitions = Column(Integer, default=0)
    next_review_date = Column(Date)
    last_reviewed = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="flashcard_reviews")
    flashcard = relationship("Flashcard", back_populates="reviews")


class Discussion(Base):
    __tablename__ = "discussions"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    parent_id = Column(Integer, ForeignKey("discussions.id"), nullable=True)
    content = Column(Text)
    upvotes = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="discussions")
    topic = relationship("Topic")
    replies = relationship("Discussion", backref="parent", remote_side=[id], cascade="all, delete-orphan", single_parent=True)

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    activity_type = Column(String) # topic_complete, quiz_submit, post, review
    activity_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

class APIUsage(Base):
    __tablename__ = "api_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    provider = Column(String, index=True)  # gemini, huggingface, flux, youtube
    action = Column(String)    # generate_course, generate_topic, tts, image, video
    latency_ms = Column(Integer)
    status = Column(String)    # success, fallback, failure
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User")

class CacheEntry(Base):
    __tablename__ = "cache_entries"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(JSON)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ApiLog(Base):
    __tablename__ = "api_logs"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    endpoint = Column(String, index=True)
    status_code = Column(Integer, index=True)
    duration = Column(Float) # In milliseconds
    ip_address = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
