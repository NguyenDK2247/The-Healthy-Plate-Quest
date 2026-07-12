"""
evaluation.py — Models for user evaluation data collection.

Stores:
  - UsabilityResponse  : SUS (System Usability Scale) questionnaire answers
  - FeedbackResponse   : Open-ended qualitative feedback
  - SessionEvent       : Lightweight analytics (page views, feature interactions)
"""

from datetime import datetime
from app import db


class UsabilityResponse(db.Model):
    """
    System Usability Scale (SUS) — 10 standardized questions.
    Each scored 1–5 (Strongly Disagree → Strongly Agree).
    SUS score = ((sum of odd items - 5) + (25 - sum of even items)) * 2.5
    A score ≥ 70 is considered above average usability.
    """
    __tablename__ = 'usability_responses'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    # SUS questions 1–10 (1 = Strongly Disagree, 5 = Strongly Agree)
    q1  = db.Column(db.Integer)   # I think I would like to use this system frequently
    q2  = db.Column(db.Integer)   # I found the system unnecessarily complex
    q3  = db.Column(db.Integer)   # I thought the system was easy to use
    q4  = db.Column(db.Integer)   # I think I would need support to use this system
    q5  = db.Column(db.Integer)   # I found the various functions well integrated
    q6  = db.Column(db.Integer)   # I thought there was too much inconsistency
    q7  = db.Column(db.Integer)   # I would imagine most people learn this quickly
    q8  = db.Column(db.Integer)   # I found the system very cumbersome to use
    q9  = db.Column(db.Integer)   # I felt very confident using the system
    q10 = db.Column(db.Integer)   # I needed to learn a lot before getting started

    # AI coach-specific questions (1–5 Likert)
    ai_coach_motivated   = db.Column(db.Integer)  # Coach Vita made me feel motivated
    ai_coach_useful      = db.Column(db.Integer)  # Coach Vita's feedback was useful
    ai_coach_personal    = db.Column(db.Integer)  # Coaching felt personalized to me
    ai_coach_trustworthy = db.Column(db.Integer)  # I trusted Coach Vita's advice

    @property
    def sus_score(self):
        """Calculate standardized SUS score (0–100)."""
        odd  = [self.q1, self.q3, self.q5, self.q7, self.q9]
        even = [self.q2, self.q4, self.q6, self.q8, self.q10]
        if any(v is None for v in odd + even):
            return None
        return ((sum(odd) - 5) + (25 - sum(even))) * 2.5

    @property
    def sus_grade(self):
        score = self.sus_score
        if score is None:
            return 'N/A'
        if score >= 85: return 'Excellent (A)'
        if score >= 72: return 'Good (B)'
        if score >= 52: return 'OK (C)'
        if score >= 38: return 'Poor (D)'
        return 'Awful (F)'

    @property
    def ai_coach_avg(self):
        vals = [self.ai_coach_motivated, self.ai_coach_useful,
                self.ai_coach_personal, self.ai_coach_trustworthy]
        valid = [v for v in vals if v is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    def __repr__(self):
        return f'<UsabilityResponse user={self.user_id} SUS={self.sus_score}>'


class FeedbackResponse(db.Model):
    """Open-ended qualitative feedback from users."""
    __tablename__ = 'feedback_responses'

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Structured open questions
    what_worked    = db.Column(db.Text)   # What did you enjoy most?
    what_didnt     = db.Column(db.Text)   # What was frustrating or confusing?
    ai_coach_comment = db.Column(db.Text) # What did you think of Coach Vita?
    suggestion     = db.Column(db.Text)   # What one feature would you add or change?
    would_recommend = db.Column(db.Boolean)  # Would you recommend this app?
    overall_rating  = db.Column(db.Integer)  # 1–5 star overall rating

    def __repr__(self):
        return f'<FeedbackResponse user={self.user_id} rating={self.overall_rating}>'


class SessionEvent(db.Model):
    """
    Lightweight analytics — logs significant user interactions.
    Used to measure feature engagement for the thesis.
    """
    __tablename__ = 'session_events'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    event_type = db.Column(db.String(64), nullable=False)
    # e.g. 'page_view', 'meal_logged', 'quest_completed', 'coach_message',
    #       'badge_earned', 'quest_generated', 'streak_shield_used'
    event_data = db.Column(db.String(256))  # optional JSON-encoded extra info
    occurred_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<SessionEvent {self.event_type} user={self.user_id}>'
    