from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.food_log import FoodLog
from app.models.quest import UserQuest
from app.models.leaderboard import LeaderboardEntry
from app.services.gamification import assign_daily_quests, assign_weekly_quests

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    # Auto-assign quests on dashboard visit
    assign_daily_quests(current_user)
    assign_weekly_quests(current_user)

    today_totals = FoodLog.get_today_totals(current_user.id)
    active_quests = UserQuest.get_active_for_user(current_user.id)[:3]
    recent_logs = FoodLog.get_today_logs(current_user.id)

    # Leaderboard rank
    week, year = LeaderboardEntry.get_current_week()
    my_entry = LeaderboardEntry.query.filter_by(
        user_id=current_user.id, week_number=week, year=year
    ).first()
    my_rank = None
    if my_entry:
        my_rank = LeaderboardEntry.query.filter(
            LeaderboardEntry.week_number == week,
            LeaderboardEntry.year == year,
            LeaderboardEntry.xp_this_week > my_entry.xp_this_week
        ).count() + 1

    return render_template('dashboard/index.html',
                           today_totals=today_totals,
                           active_quests=active_quests,
                           recent_logs=recent_logs,
                           my_rank=my_rank,
                           my_entry=my_entry)
