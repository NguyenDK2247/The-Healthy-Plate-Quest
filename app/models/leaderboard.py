from datetime import datetime
from app import db


class LeaderboardEntry(db.Model):
    """Weekly leaderboard snapshot — refreshed each week."""
    __tablename__ = 'leaderboard_entries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # ISO week number + year to group entries
    week_number = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)

    xp_this_week = db.Column(db.Integer, default=0)
    meals_logged = db.Column(db.Integer, default=0)
    quests_completed = db.Column(db.Integer, default=0)
    rank = db.Column(db.Integer)  # Computed and stored each week

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'week_number', 'year', name='unique_user_week'),
    )

    @classmethod
    def get_current_week(cls):
        now = datetime.utcnow()
        return now.isocalendar()[1], now.year  # (week_number, year)

    @classmethod
    def get_weekly_rankings(cls, limit=20):
        week, year = cls.get_current_week()
        return cls.query.filter_by(week_number=week, year=year)\
                        .order_by(cls.xp_this_week.desc())\
                        .limit(limit).all()

    @classmethod
    def upsert_entry(cls, user_id, xp_delta=0, meals_delta=0, quests_delta=0):
        """Add XP/meals/quests to this week's leaderboard entry for a user."""
        week, year = cls.get_current_week()
        entry = cls.query.filter_by(user_id=user_id, week_number=week, year=year).first()
        if entry is None:
            entry = cls(user_id=user_id, week_number=week, year=year)
            db.session.add(entry)
        entry.xp_this_week += xp_delta
        entry.meals_logged += meals_delta
        entry.quests_completed += quests_delta
        db.session.commit()
        return entry

    def __repr__(self):
        return f'<LeaderboardEntry user={self.user_id} week={self.week_number}/{self.year} xp={self.xp_this_week}>'
