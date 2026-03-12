from flask import Blueprint, render_template
from flask_login import login_required
from app.models.leaderboard import LeaderboardEntry

leaderboard_bp = Blueprint('leaderboard', __name__)


@leaderboard_bp.route('/')
@login_required
def index():
    rankings = LeaderboardEntry.get_weekly_rankings()
    return render_template('leaderboard/index.html', rankings=rankings)