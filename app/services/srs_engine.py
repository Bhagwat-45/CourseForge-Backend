"""
Spaced Repetition Service — SM-2 algorithm implementation.
Based on the SuperMemo 2 algorithm used by Anki.
"""
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.models.models import FlashcardReview, Flashcard


def calculate_sm2(quality: int, ease_factor: float, interval: int, repetitions: int):
    """
    SM-2 algorithm core.
    
    Args:
        quality: User's self-rating (0-5)
            0 = complete blackout
            1 = wrong, but recognized answer
            2 = wrong, but easy to recall
            3 = correct with serious difficulty
            4 = correct with some hesitation
            5 = perfect recall
        ease_factor: Current ease factor (starts at 2.5)
        interval: Current interval in days
        repetitions: Number of successful repetitions
    
    Returns:
        (new_ease_factor, new_interval, new_repetitions)
    """
    # Minimum ease factor
    MIN_EF = 1.3

    if quality < 3:
        # Failed: reset to beginning
        return max(MIN_EF, ease_factor), 1, 0
    
    # Success: update ease factor
    new_ef = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ef = max(MIN_EF, new_ef)
    
    if repetitions == 0:
        new_interval = 1
    elif repetitions == 1:
        new_interval = 6
    else:
        new_interval = round(interval * new_ef)

    return new_ef, new_interval, repetitions + 1


def get_due_cards(db: Session, user_id: int, limit: int = 20):
    """Returns flashcards due for review today, sorted by priority."""
    today = date.today()

    # Get cards with existing reviews that are due
    due_reviews = db.query(FlashcardReview).filter(
        FlashcardReview.user_id == user_id,
        FlashcardReview.next_review_date <= today
    ).order_by(FlashcardReview.next_review_date.asc()).limit(limit).all()

    results = []
    for review in due_reviews:
        card = review.flashcard
        if card:
            results.append({
                "review_id": review.id,
                "flashcard_id": card.id,
                "front": card.front,
                "back": card.back,
                "course_id": card.course_id,
                "ease_factor": review.ease_factor,
                "interval_days": review.interval_days,
                "repetitions": review.repetitions,
            })

    return results


def review_card(db: Session, user_id: int, flashcard_id: int, quality: int):
    """
    Process a review submission for a flashcard.
    Creates or updates the FlashcardReview record.
    
    Args:
        quality: 0-5 (maps from UI: Again=1, Hard=2, Good=4, Easy=5)
    """
    quality = max(0, min(5, quality))  # Clamp to 0-5
    today = date.today()

    review = db.query(FlashcardReview).filter(
        FlashcardReview.user_id == user_id,
        FlashcardReview.flashcard_id == flashcard_id,
    ).first()

    if not review:
        review = FlashcardReview(
            user_id=user_id,
            flashcard_id=flashcard_id,
            ease_factor=2.5,
            interval_days=1,
            repetitions=0,
            next_review_date=today,
        )
        db.add(review)

    new_ef, new_interval, new_reps = calculate_sm2(
        quality, review.ease_factor, review.interval_days, review.repetitions
    )

    review.ease_factor = new_ef
    review.interval_days = new_interval
    review.repetitions = new_reps
    review.next_review_date = today + timedelta(days=new_interval)

    db.commit()

    return {
        "flashcard_id": flashcard_id,
        "new_ease_factor": round(new_ef, 2),
        "new_interval_days": new_interval,
        "next_review_date": str(review.next_review_date),
        "repetitions": new_reps,
    }


def init_srs_for_course(db: Session, user_id: int, course_id: int):
    """
    Initialize SRS review records for all flashcards in a course
    that the user hasn't started reviewing yet.
    """
    today = date.today()
    
    existing_ids = set(
        r.flashcard_id for r in db.query(FlashcardReview.flashcard_id).filter(
            FlashcardReview.user_id == user_id
        ).all()
    )

    cards = db.query(Flashcard).filter(Flashcard.course_id == course_id).all()
    new_count = 0

    for card in cards:
        if card.id not in existing_ids:
            review = FlashcardReview(
                user_id=user_id,
                flashcard_id=card.id,
                ease_factor=2.5,
                interval_days=1,
                repetitions=0,
                next_review_date=today,
            )
            db.add(review)
            new_count += 1

    db.commit()
    return new_count
