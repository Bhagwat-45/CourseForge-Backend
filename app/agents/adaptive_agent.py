"""
Adaptive Difficulty Agent — recommends content level based on quiz performance.
"""

def recommend_difficulty(quiz_scores: dict) -> str:
    """
    Analyzes quiz scores and returns the recommended difficulty level.
    
    Args:
        quiz_scores: dict mapping topic_id -> score (0-100)
    
    Returns:
        'beginner', 'intermediate', or 'expert'
    """
    if not quiz_scores:
        return "beginner"

    scores = list(quiz_scores.values())
    
    # Filter out non-numeric values
    numeric_scores = [s for s in scores if isinstance(s, (int, float))]
    if not numeric_scores:
        return "beginner"
    
    avg = sum(numeric_scores) / len(numeric_scores)
    recent_scores = numeric_scores[-5:]  # Weight recent performance more
    recent_avg = sum(recent_scores) / len(recent_scores)
    
    # Weighted average: 40% overall, 60% recent
    weighted = (avg * 0.4) + (recent_avg * 0.6)

    if weighted >= 85:
        return "expert"
    elif weighted >= 55:
        return "intermediate"
    else:
        return "beginner"
