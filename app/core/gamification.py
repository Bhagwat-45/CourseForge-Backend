from sqlalchemy.orm import Session
from app.models.models import User, ActivityLog

# Badge Definitions
BADGES = {
    "architect": {"name": "The Architect", "icon": "🏗️", "description": "Complete 3 courses at Advanced level"},
    "code_weaver": {"name": "Code Weaver", "icon": "🕸️", "description": "Solve 5 Lab Workshops"},
    "persistent": {"name": "Unstoppable", "icon": "⚡", "description": "Reach a 7-day learning streak"},
    "nova_fan": {"name": "Nova's Favorite", "icon": "🤖", "description": "Interact with Nova 50 times"},
}

def award_xp(db: Session, user: User, amount: int, activity_type: str = "general", metadata: dict = None):
    """Awards XP, checks for level ups, and logs activity."""
    user.xp += amount
    
    # Log the activity
    log = ActivityLog(
        user_id=user.id,
        activity_type=activity_type,
        activity_metadata=metadata
    )
    db.add(log)
    
    # Simple Leveling logic: Level = 1 + floor(sqrt(XP / 1000))
    new_level = int(1 + (user.xp / 1000)**0.5)
    if new_level > user.level:
        user.level = new_level
        return True
    return False

def check_and_award_badges(db: Session, user: User):
    """Scans user activity and awards badges."""
    new_badges = []
    current_badges = set(user.badges or [])
    
    # Logic for 'Code Weaver'
    # This would normally query another table, but for now let's use a simple check
    # if user.total_labs_completed >= 5 and "code_weaver" not in current_badges:
    #     new_badges.append("code_weaver")
    
    if new_badges:
        user.badges = list(current_badges.union(new_badges))
        db.commit()
    
    return new_badges
