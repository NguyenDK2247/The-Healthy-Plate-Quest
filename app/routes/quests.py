from flask import Blueprint, render_template
from flask_login import login_required

quests_bp = Blueprint('quests', __name__)

@quests_bp.route('/')
@login_required
def index():
    return render_template('quests/index.html')