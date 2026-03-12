from flask import Blueprint, render_template
from flask_login import login_required

food_log_bp = Blueprint('food_log', __name__)

@food_log_bp.route('/')
@login_required
def index():
    return render_template('food_log/index.html')