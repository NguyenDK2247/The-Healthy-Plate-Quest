from datetime import datetime, date, timedelta
from app import db


class Quest(db.Model):
    """Template quests — static definitions of available challenges."""
    __tablename__ = 'quests'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=False)
    quest_type = db.Column(db.String(32))       # 'daily', 'weekly', 'special', 'ai_generated'
    category = db.Column(db.String(64))          # 'vegetables', 'protein', 'variety', 'hydration', etc.
    difficulty = db.Column(db.String(16))        # 'easy', 'medium', 'hard'
    xp_reward = db.Column(db.Integer, default=50)
    badge_reward_id = db.Column(db.Integer, db.ForeignKey('badges.id'), nullable=True)
    icon = db.Column(db.String(64), default='🥗')

    # Completion criteria (JSON-like stored as string or use JSON column)
    # e.g., "log_3_vegetables" / "eat_5_colors" / "log_protein_4_days"
    criteria_type = db.Column(db.String(64))
    criteria_target = db.Column(db.Integer, default=1)  # target count

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # For AI-generated quests, link to the user who got it
    ai_generated_for_user = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    user_quests = db.relationship('UserQuest', backref='quest', lazy='dynamic')

    def __repr__(self):
        return f'<Quest "{self.title}" ({self.quest_type}, {self.xp_reward} XP)>'


class UserQuest(db.Model):
    """Tracks a specific user's progress on a quest."""
    __tablename__ = 'user_quests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quest_id = db.Column(db.Integer, db.ForeignKey('quests.id'), nullable=False)

    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)  # For daily/weekly quests

    progress = db.Column(db.Integer, default=0)     # Current count toward target
    is_completed = db.Column(db.Boolean, default=False)
    xp_claimed = db.Column(db.Boolean, default=False)

    def progress_percent(self):
        if self.quest.criteria_target == 0:
            return 100
        return min(100, int((self.progress / self.quest.criteria_target) * 100))

    def is_expired(self):
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def complete(self):
        self.is_completed = True
        self.completed_at = datetime.utcnow()
        db.session.commit()

    @classmethod
    def get_active_for_user(cls, user_id):
        now = datetime.utcnow()
        return cls.query.filter(
            cls.user_id == user_id,
            cls.is_completed == False,
            db.or_(cls.expires_at == None, cls.expires_at > now)
        ).all()

    def __repr__(self):
        return f'<UserQuest user={self.user_id} quest={self.quest_id} progress={self.progress}>'
