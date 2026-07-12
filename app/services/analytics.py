"""
analytics.py — Analytics and data export service for Phase 7.

Provides:
  - log_event()        : Record a session event for a user
  - get_user_stats()   : Full stats summary for one user
  - get_study_export() : CSV-ready data export for thesis analysis
  - get_sus_summary()  : Aggregate SUS scores across all participants
"""

import csv
import io
import json
from datetime import datetime, date, timedelta
from app import db
from app.models.evaluation import UsabilityResponse, FeedbackResponse, SessionEvent
from app.models.food_log import FoodLog
from app.models.quest import UserQuest
from app.models.badge import UserBadge
from app.models.user import User


def log_event(user_id, event_type, event_data=None):
    """Record a session event. Call this from any route to track engagement."""
    try:
        ev = SessionEvent(
            user_id=user_id,
            event_type=event_type,
            event_data=json.dumps(event_data) if event_data else None,
        )
        db.session.add(ev)
        db.session.commit()
    except Exception:
        pass  # Never let analytics break the app


def get_user_stats(user):
    """Return a comprehensive stats dict for a single user."""
    from app.models.leaderboard import LeaderboardEntry

    # Session events breakdown
    events = SessionEvent.query.filter_by(user_id=user.id).all()
    event_counts = {}
    for ev in events:
        event_counts[ev.event_type] = event_counts.get(ev.event_type, 0) + 1

    # Food log stats
    logs = FoodLog.query.filter_by(user_id=user.id).all()
    avg_calories = round(sum(l.calories for l in logs) / len(logs), 1) if logs else 0
    categories   = {}
    for log in logs:
        cat = log.food_category or 'other'
        categories[cat] = categories.get(cat, 0) + 1

    # Days active (unique dates with a log)
    active_dates = {log.logged_at.date() for log in logs}
    days_since_join = max(1, (date.today() - user.created_at.date()).days)

    # Quests
    completed_quests = UserQuest.query.filter_by(
        user_id=user.id, is_completed=True
    ).count()
    ai_quests = UserQuest.query.join(
        UserQuest.quest
    ).filter(
        UserQuest.user_id == user.id,
        db.text("quests.quest_type = 'ai_generated'"),
    ).count()

    # Coach interactions
    coach_messages = event_counts.get('coach_message', 0)

    # SUS score
    sus = UsabilityResponse.query.filter_by(user_id=user.id).order_by(
        UsabilityResponse.submitted_at.desc()
    ).first()

    # Feedback
    feedback = FeedbackResponse.query.filter_by(user_id=user.id).order_by(
        FeedbackResponse.submitted_at.desc()
    ).first()

    return {
        'user_id':          user.id,
        'username':         user.username,
        'age':              user.age,
        'nutrition_goal':   user.nutrition_goal,
        'dietary_pref':     user.dietary_preference,
        'days_since_join':  days_since_join,
        'days_active':      len(active_dates),
        'engagement_rate':  round(len(active_dates) / days_since_join * 100, 1),
        'total_meals':      user.total_meals_logged or 0,
        'avg_calories':     avg_calories,
        'food_categories':  categories,
        'xp_points':        user.xp_points or 0,
        'level':            user.level,
        'current_streak':   user.current_streak or 0,
        'longest_streak':   user.longest_streak or 0,
        'quests_completed': completed_quests,
        'ai_quests':        ai_quests,
        'badges_earned':    UserBadge.query.filter_by(user_id=user.id).count(),
        'coach_messages':   coach_messages,
        'event_counts':     event_counts,
        'sus_score':        sus.sus_score if sus else None,
        'sus_grade':        sus.sus_grade if sus else None,
        'ai_coach_avg':     sus.ai_coach_avg if sus else None,
        'overall_rating':   feedback.overall_rating if feedback else None,
        'would_recommend':  feedback.would_recommend if feedback else None,
    }


def get_sus_summary():
    """Aggregate SUS scores across all participants who submitted a response."""
    responses = UsabilityResponse.query.all()
    if not responses:
        return None

    scores = [r.sus_score for r in responses if r.sus_score is not None]
    ai_avgs = [r.ai_coach_avg for r in responses if r.ai_coach_avg is not None]

    if not scores:
        return None

    return {
        'n':           len(scores),
        'mean':        round(sum(scores) / len(scores), 2),
        'min':         round(min(scores), 2),
        'max':         round(max(scores), 2),
        'above_70':    sum(1 for s in scores if s >= 70),
        'ai_coach_mean': round(sum(ai_avgs) / len(ai_avgs), 2) if ai_avgs else None,
        'grades':      {
            'Excellent': sum(1 for s in scores if s >= 85),
            'Good':      sum(1 for s in scores if 72 <= s < 85),
            'OK':        sum(1 for s in scores if 52 <= s < 72),
            'Poor':      sum(1 for s in scores if 38 <= s < 52),
            'Awful':     sum(1 for s in scores if s < 38),
        },
    }


def generate_csv_export():
    """
    Generate a CSV file of all user stats for thesis analysis.
    Returns a string buffer ready to be sent as a file download.
    """
    users = User.query.all()
    output = io.StringIO()

    fieldnames = [
        'user_id', 'username', 'age', 'nutrition_goal', 'dietary_pref',
        'days_since_join', 'days_active', 'engagement_rate',
        'total_meals', 'avg_calories', 'xp_points', 'level',
        'current_streak', 'longest_streak', 'quests_completed',
        'ai_quests', 'badges_earned', 'coach_messages',
        'sus_score', 'sus_grade', 'ai_coach_avg',
        'overall_rating', 'would_recommend',
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()

    for user in users:
        stats = get_user_stats(user)
        writer.writerow(stats)

    output.seek(0)
    return output.getvalue()
