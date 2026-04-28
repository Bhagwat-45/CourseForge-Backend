from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import User
import logging

logger = logging.getLogger("courseforge.usage")
router = APIRouter()

@router.get("/usage")
def get_usage(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns current user's generation usage statistics with reset logic."""
    now = datetime.now(timezone.utc)
    
    # Ensure cycle dates exist initally
    if not current_user.cycle_end_date:
        current_user.cycle_start_date = now
        current_user.cycle_end_date = now + timedelta(days=30)
        db.commit()

    # Reset if cycle ended
    if now > current_user.cycle_end_date.replace(tzinfo=timezone.utc):
        logger.info(f"[USAGE_RESET] Resetting usage for {current_user.email} via /usage.")
        current_user.generation_count = 0
        current_user.cycle_start_date = now
        current_user.cycle_end_date = now + timedelta(days=30)
        db.commit()

    return {
        "generation_count": current_user.generation_count,
        "limit": 5,
        "cycle_end_date": current_user.cycle_end_date
    }
