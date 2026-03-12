from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Profile
    display_name = db.Column(db.String(64))
    avatar_url = db.Column(db.String(256), default='default_avatar.png')
    bio = db.Column(db.String(280))

    # Target group / onboarding
    age = db.Column(db.Integer)
    # Goal: 'energy', 'weight_management', 'gut_health', 'muscle_building', 'general'
    nutrition_goal = db.Column(db.String(64), default='general')
    # e.g., 'omnivore', 'vegetarian', 'vegan', 'pescatarian'
    dietary_preference = db.Column(db.String(64), default='omnivore')
    dietary_restrictions = db.Column(db.String(256))  # comma-separated e.g. 'gluten,lactose'
    favorite_ingredients = db.Column(db.String(512))  # comma-separated

    # Gamification stats
    xp_points = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    current_streak = db.Column(db.Integer, default=0)
    longest_streak = db.Column(db.Integer, default=0)
    last_log_date = db.Column(db.Date)
    total_meals_logged = db.Column(db.Integer, default=0)
    total_quests_completed = db.Column(db.Integer, default=0)

    # Relationships
    food_logs = db.relationship('FoodLog', backref='user', lazy='dynamic',
                                 cascade='all, delete-orphan')
    user_quests = db.relationship('UserQuest', backref='user', lazy='dynamic',
                                   cascade='all, delete-orphan')
    badges = db.relationship('UserBadge', backref='user', lazy='dynamic',
                              cascade='all, delete-orphan')
    leaderboard_entries = db.relationship('LeaderboardEntry', backref='user',
                                           lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def add_xp(self, amount, reason=''):
        """Award XP and check for level-up."""
        self.xp_points += amount
        new_level = self._calculate_level(self.xp_points)
        leveled_up = new_level > self.level
        self.level = new_level
        db.session.commit()
        return leveled_up

    def _calculate_level(self, xp):
        """Level thresholds: each level requires 200 * level XP."""
        level = 1
        threshold = 0
        while True:
            threshold += 200 * level
            if xp < threshold:
                return level
            level += 1

    def xp_for_next_level(self):
        """XP needed to reach the next level."""
        current_threshold = sum(200 * i for i in range(1, self.level))
        next_threshold = current_threshold + 200 * self.level
        return next_threshold - self.xp_points

    def xp_progress_percent(self):
        """Percentage progress toward next level (0–100)."""
        current_threshold = sum(200 * i for i in range(1, self.level))
        next_threshold = current_threshold + 200 * self.level
        xp_in_level = self.xp_points - current_threshold
        level_range = next_threshold - current_threshold
        return min(100, int((xp_in_level / level_range) * 100))

    def update_streak(self):
        """Call once per day when a meal is logged."""
        today = date.today()
        if self.last_log_date is None:
            self.current_streak = 1
        elif self.last_log_date == today:
            return  # Already logged today
        elif (today - self.last_log_date).days == 1:
            self.current_streak += 1
        else:
            self.current_streak = 1  # Streak broken
        self.last_log_date = today
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
        db.session.commit()

    @property
    def level_title(self):
        titles = {
            1: 'Curious Nibbler',
            2: 'Snack Scout',
            3: 'Plate Padawan',
            4: 'Veggie Voyager',
            5: 'Macro Maestro',
            6: 'Nutrition Ninja',
            7: 'Balance Keeper',
            8: 'Wellness Warrior',
            9: 'Health Champion',
            10: 'Plate Master',
        }
        return titles.get(self.level, f'Level {self.level} Expert')

    def __repr__(self):
        return f'<User {self.username} | Level {self.level} | {self.xp_points} XP>'
