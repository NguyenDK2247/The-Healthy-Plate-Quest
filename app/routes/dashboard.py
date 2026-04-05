from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.food_log import FoodLog
from app.models.quest import UserQuest
from app.models.leaderboard import LeaderboardEntry
from app.services.gamification import assign_daily_quests, assign_weekly_quests, check_streak_protection
from app.services.nudges import generate_nudges, get_weekly_summary

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    # Auto-assign quests on dashboard visit
    assign_daily_quests(current_user)
    assign_weekly_quests(current_user)

    today_totals  = FoodLog.get_today_totals(current_user.id)
    active_quests = UserQuest.get_active_for_user(current_user.id)[:3]
    recent_logs   = FoodLog.get_today_logs(current_user.id)

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

    # Phase 6: Behavioural nudges + weekly summary
    nudges         = generate_nudges(current_user, today_totals)
    weekly_summary = get_weekly_summary(current_user)

    streak_shield_available = check_streak_protection(current_user)

    return render_template('dashboard/index.html',
                           today_totals=today_totals,
                           active_quests=active_quests,
                           recent_logs=recent_logs,
                           my_rank=my_rank,
                           my_entry=my_entry,
                           nudges=nudges,
                           weekly_summary=weekly_summary,
                           streak_shield_available=streak_shield_available)


from flask import request, flash, redirect, url_for
from app.services.gamification import check_streak_protection, apply_streak_shield


@dashboard_bp.route('/streak-shield', methods=['POST'])
@login_required
def streak_shield():
    """Spend 50 XP to repair a 1-day missed streak."""
    if not check_streak_protection(current_user):
        flash('Streak shield is not available right now.', 'info')
        return redirect(url_for('dashboard.index'))

    if apply_streak_shield(current_user):
        flash('🛡️ Streak shield activated! Your streak has been restored for 50 XP.', 'success')
    else:
        flash('Not enough XP for a streak shield (costs 50 XP).', 'warning')

    return redirect(url_for('dashboard.index'))
