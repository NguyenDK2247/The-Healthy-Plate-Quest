from datetime import datetime
from app import db


class FoodLog(db.Model):
    __tablename__ = 'food_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    logged_at = db.Column(db.DateTime, default=datetime.utcnow)
    meal_type = db.Column(db.String(32))  # 'breakfast', 'lunch', 'dinner', 'snack'

    # Food item info
    food_name = db.Column(db.String(128), nullable=False)
    brand = db.Column(db.String(128))
    quantity_g = db.Column(db.Float, default=100.0)  # grams

    # Macronutrients (per logged quantity)
    calories = db.Column(db.Float, default=0)
    protein_g = db.Column(db.Float, default=0)
    carbs_g = db.Column(db.Float, default=0)
    fat_g = db.Column(db.Float, default=0)
    fiber_g = db.Column(db.Float, default=0)
    sugar_g = db.Column(db.Float, default=0)
    sodium_mg = db.Column(db.Float, default=0)

    # Categorization (for quest tracking)
    food_category = db.Column(db.String(64))   # e.g., 'vegetable', 'fruit', 'protein', 'grain', 'dairy'
    color_group = db.Column(db.String(32))      # e.g., 'red', 'green', 'orange' for color variety quests
    is_whole_food = db.Column(db.Boolean, default=False)
    is_plant_based = db.Column(db.Boolean, default=False)

    # AI feedback
    ai_feedback = db.Column(db.Text)
    ai_feedback_generated_at = db.Column(db.DateTime)

    # XP awarded for this log
    xp_awarded = db.Column(db.Integer, default=10)

    def __repr__(self):
        return f'<FoodLog {self.food_name} ({self.calories} kcal) by user {self.user_id}>'

    @classmethod
    def get_today_logs(cls, user_id):
        today = datetime.utcnow().date()
        return cls.query.filter(
            cls.user_id == user_id,
            db.func.date(cls.logged_at) == today
        ).all()

    @classmethod
    def get_today_totals(cls, user_id):
        logs = cls.get_today_logs(user_id)
        return {
            'calories': sum(l.calories for l in logs),
            'protein_g': sum(l.protein_g for l in logs),
            'carbs_g': sum(l.carbs_g for l in logs),
            'fat_g': sum(l.fat_g for l in logs),
            'fiber_g': sum(l.fiber_g for l in logs),
            'meal_count': len(logs)
        }
