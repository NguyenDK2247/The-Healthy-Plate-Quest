from flask import Blueprint, render_template
from flask_login import login_required

coach_bp = Blueprint('coach', __name__)

@coach_bp.route('/')
@login_required
def index():
    return render_template('coach/index.html')