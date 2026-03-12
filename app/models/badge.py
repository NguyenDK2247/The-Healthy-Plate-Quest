from datetime import datetime
from app import db


class Badge(db.Model):
    """Badge definitions."""
    __tablename__ = 'badges'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True)
    description = db.Column(db.String(256))
    icon = db.Column(db.String(64), default='🏅')   # emoji or filename
    category = db.Column(db.String(64))             # 'streak', 'logging', 'nutrition', 'social', 'quest'
    rarity = db.Column(db.String(16), default='common')  # 'common', 'rare', 'epic', 'legendary'

    # Unlock condition (for automatic awarding logic)
    trigger_type = db.Column(db.String(64))   # 'streak_days', 'meals_logged', 'quests_completed', etc.
    trigger_value = db.Column(db.Integer)     # e.g., 7 for a 7-day streak

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_badges = db.relationship('UserBadge', backref='badge', lazy='dynamic')

    def __repr__(self):
        return f'<Badge "{self.name}" [{self.rarity}]>'


class UserBadge(db.Model):
    """Tracks which badges a user has earned."""
    __tablename__ = 'user_badges'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey('badges.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_featured = db.Column(db.Boolean, default=False)  # User can pin up to 3 badges

    __table_args__ = (
        db.UniqueConstraint('user_id', 'badge_id', name='unique_user_badge'),
    )

    def __repr__(self):
        return f'<UserBadge user={self.user_id} badge={self.badge_id}>'


# Seed data helper — call once via CLI or migration
DEFAULT_BADGES = [
    # Streak badges
    {'name': 'First Step',       'icon': '👣', 'category': 'logging',  'rarity': 'common',    'trigger_type': 'meals_logged',      'trigger_value': 1,   'description': 'Log your very first meal.'},
    {'name': 'On a Roll',        'icon': '🔥', 'category': 'streak',   'rarity': 'common',    'trigger_type': 'streak_days',       'trigger_value': 3,   'description': 'Maintain a 3-day logging streak.'},
    {'name': 'Week Warrior',     'icon': '📅', 'category': 'streak',   'rarity': 'rare',      'trigger_type': 'streak_days',       'trigger_value': 7,   'description': 'Log meals for 7 days in a row.'},
    {'name': 'Unstoppable',      'icon': '⚡', 'category': 'streak',   'rarity': 'epic',      'trigger_type': 'streak_days',       'trigger_value': 30,  'description': 'Maintain a 30-day streak!'},
    # Logging badges
    {'name': 'Meal Tracker',     'icon': '📋', 'category': 'logging',  'rarity': 'common',    'trigger_type': 'meals_logged',      'trigger_value': 10,  'description': 'Log 10 meals total.'},
    {'name': 'Food Journalist',  'icon': '📰', 'category': 'logging',  'rarity': 'rare',      'trigger_type': 'meals_logged',      'trigger_value': 50,  'description': 'Log 50 meals total.'},
    # Quest badges
    {'name': 'Quest Starter',    'icon': '⚔️', 'category': 'quest',    'rarity': 'common',    'trigger_type': 'quests_completed',  'trigger_value': 1,   'description': 'Complete your first quest.'},
    {'name': 'Quest Champion',   'icon': '🏆', 'category': 'quest',    'rarity': 'epic',      'trigger_type': 'quests_completed',  'trigger_value': 20,  'description': 'Complete 20 quests.'},
    # Nutrition badges
    {'name': 'Rainbow Eater',    'icon': '🌈', 'category': 'nutrition','rarity': 'rare',      'trigger_type': 'color_variety',     'trigger_value': 5,   'description': 'Eat 5 different colored foods in one day.'},
    {'name': 'Protein Pro',      'icon': '💪', 'category': 'nutrition','rarity': 'common',    'trigger_type': 'protein_goal',      'trigger_value': 7,   'description': 'Hit your protein goal 7 days in a row.'},
    {'name': 'Fiber Friend',     'icon': '🌾', 'category': 'nutrition','rarity': 'common',    'trigger_type': 'fiber_logged',      'trigger_value': 25,  'description': 'Log a meal with over 25g of fiber.'},
    # Special
    {'name': 'Plate Master',     'icon': '👑', 'category': 'special',  'rarity': 'legendary', 'trigger_type': 'level_reached',     'trigger_value': 10,  'description': 'Reach Level 10 — the ultimate Plate Master!'},
]
