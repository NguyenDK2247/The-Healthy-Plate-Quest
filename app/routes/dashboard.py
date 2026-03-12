from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.food_log import FoodLog
from app.models.quest import UserQuest

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    today_totals = FoodLog.get_today_totals(current_user.id)
    active_quests = UserQuest.get_active_for_user(current_user.id)[:3]
    recent_logs = FoodLog.get_today_logs(current_user.id)

    return render_template('dashboard/index.html',
                           today_totals=today_totals,
                           active_quests=active_quests,
                           recent_logs=recent_logs)