from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.leaderboard import LeaderboardEntry
from app.models.user import User

leaderboard_bp = Blueprint('leaderboard', __name__)


@leaderboard_bp.route('/')
@login_required
def index():
    rankings = LeaderboardEntry.get_weekly_rankings(limit=20)

    ranked = []
    for i, entry in enumerate(rankings, start=1):
        user = User.query.get(entry.user_id)
        ranked.append({'rank': i, 'entry': entry, 'user': user,
                       'is_me': entry.user_id == current_user.id})

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

    return render_template('leaderboard/index.html',
                           ranked=ranked, my_entry=my_entry, my_rank=my_rank)
