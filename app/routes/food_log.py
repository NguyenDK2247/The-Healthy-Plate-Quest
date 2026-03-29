from datetime import datetime, date
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.food_log import FoodLog
from app.models.leaderboard import LeaderboardEntry
from app.services.gamification import (
    award_xp, process_streak, update_quest_progress,
    check_and_award_badges, build_reward_summary, XP_EVENTS
)

food_log_bp = Blueprint('food_log', __name__)

# Lazy import to avoid circular imports
def _get_meal_feedback(user, log):
    try:
        from app.services.ai_coach import generate_meal_feedback
        return generate_meal_feedback(user, log)
    except Exception:
        return None


# ─── USDA FoodData Central search ───────────────────────────────────────────
import requests

USDA_API_KEY = 'FcjpycpiZSCaYOHivFV2C7fb8clKcPKAekYvHAHm'

def search_usda(query, max_results=8):
    """Search USDA FoodData Central and return simplified results."""
    try:
        url = 'https://api.nal.usda.gov/fdc/v1/foods/search'
        params = {
            'query': query,
            'api_key': USDA_API_KEY,
            'pageSize': max_results,
            'dataType': 'Survey (FNDDS),SR Legacy,Foundation',
        }
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for food in data.get('foods', []):
            nutrients = {n['nutrientName']: n['value']
                         for n in food.get('foodNutrients', [])}
            results.append({
                'fdc_id':   food.get('fdcId'),
                'name':     food.get('description', '').title(),
                'brand':    food.get('brandOwner', ''),
                'calories': round(nutrients.get('Energy', 0), 1),
                'protein':  round(nutrients.get('Protein', 0), 1),
                'carbs':    round(nutrients.get('Carbohydrate, by difference', 0), 1),
                'fat':      round(nutrients.get('Total lipid (fat)', 0), 1),
                'fiber':    round(nutrients.get('Fiber, total dietary', 0), 1),
                'sugar':    round(nutrients.get('Sugars, total including NLEA', 0), 1),
                'sodium':   round(nutrients.get('Sodium, Na', 0), 1),
            })
        return results
    except Exception:
        return []


# ─── Helpers ────────────────────────────────────────────────────────────────

# Maps food categories to quest criteria types (for gamification engine)
CATEGORY_QUEST_MAP = {
    'vegetable': ['log_vegetables', 'log_vegetables_week'],
    'fruit':     ['log_fruit'],
    'protein':   ['log_protein', 'log_protein_days'],
    'grain':     [],
    'dairy':     [],
    'other':     [],
}

# Simple color group mapping by category
CATEGORY_COLOR_MAP = {
    'vegetable': 'green',
    'fruit':     'red',
    'protein':   'brown',
    'grain':     'yellow',
    'dairy':     'white',
}


def process_food_log_rewards(user, log):
    """
    After saving a FoodLog, trigger all gamification:
    XP, streaks, quest progress, badges, leaderboard.
    Returns flash messages.
    """
    all_quest_results = []

    # Base XP for logging
    xp_amount = XP_EVENTS['log_meal']

    # Bonus if all macros filled in
    if log.protein_g and log.carbs_g and log.fat_g:
        xp_amount = XP_EVENTS['log_meal_complete']

    # First meal bonus
    today_count = FoodLog.query.filter(
        FoodLog.user_id == user.id,
        db.func.date(FoodLog.logged_at) == date.today()
    ).count()
    if today_count == 1:
        xp_amount += XP_EVENTS['first_meal_today']

    log.xp_awarded = xp_amount
    user.total_meals_logged += 1
    db.session.commit()

    xp_result = award_xp(user, xp_amount, reason=f'Logged {log.food_name}')
    LeaderboardEntry.upsert_entry(user.id, meals_delta=1)

    # Streak
    streak_result = process_streak(user)

    # Quest progress — general meal logging
    all_quest_results += update_quest_progress(user, 'log_meals_week', 1)

    # Meal-type specific quests
    if log.meal_type == 'breakfast':
        all_quest_results += update_quest_progress(user, 'log_breakfast', 1)

    # Category-based quests
    if log.food_category:
        for criteria in CATEGORY_QUEST_MAP.get(log.food_category, []):
            all_quest_results += update_quest_progress(user, criteria, 1)

    # Color variety quest
    if log.color_group:
        today_colors = {
            fl.color_group for fl in FoodLog.get_today_logs(user.id)
            if fl.color_group
        }
        if len(today_colors) >= 5:
            all_quest_results += update_quest_progress(user, 'color_variety', 1)

    # Fiber goal quest
    today_totals = FoodLog.get_today_totals(user.id)
    if today_totals['fiber_g'] >= 25:
        all_quest_results += update_quest_progress(user, 'daily_fiber_goal', 1)

    # Badge checks
    check_and_award_badges(user, 'meals_logged', user.total_meals_logged)

    return build_reward_summary(
        xp_result=xp_result,
        streak_result=streak_result,
        quest_results=all_quest_results
    )


# ─── Routes ─────────────────────────────────────────────────────────────────

@food_log_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        food_name    = request.form.get('food_name', '').strip()
        meal_type    = request.form.get('meal_type', 'snack')
        quantity_g   = float(request.form.get('quantity_g') or 100)
        food_category = request.form.get('food_category', 'other')

        if not food_name:
            flash('Please enter a food name.', 'danger')
            return redirect(url_for('food_log.index'))

        # Scale nutrients from per-100g values to actual quantity
        scale = quantity_g / 100.0

        log = FoodLog(
            user_id      = current_user.id,
            food_name    = food_name,
            brand        = request.form.get('brand', ''),
            meal_type    = meal_type,
            quantity_g   = quantity_g,
            food_category = food_category,
            color_group  = CATEGORY_COLOR_MAP.get(food_category, 'other'),
            is_plant_based = food_category in ('vegetable', 'fruit', 'grain'),
            calories     = round(float(request.form.get('calories') or 0) * scale, 1),
            protein_g    = round(float(request.form.get('protein') or 0) * scale, 1),
            carbs_g      = round(float(request.form.get('carbs') or 0) * scale, 1),
            fat_g        = round(float(request.form.get('fat') or 0) * scale, 1),
            fiber_g      = round(float(request.form.get('fiber') or 0) * scale, 1),
            sugar_g      = round(float(request.form.get('sugar') or 0) * scale, 1),
            sodium_mg    = round(float(request.form.get('sodium') or 0) * scale, 1),
        )
        db.session.add(log)
        db.session.commit()

        # Trigger all gamification
        messages = process_food_log_rewards(current_user, log)
        for cat, msg in messages:
            flash(msg, cat)

        flash(f'✅ {food_name} logged successfully!', 'success')

        # Generate AI meal feedback (non-blocking — skip if API unavailable)
        feedback = _get_meal_feedback(current_user, log)
        if feedback:
            log.ai_feedback = feedback
            from datetime import datetime
            log.ai_feedback_generated_at = datetime.utcnow()
            db.session.commit()

        return redirect(url_for('food_log.index'))

    # GET — show today's logs
    today_logs  = FoodLog.get_today_logs(current_user.id)
    today_totals = FoodLog.get_today_totals(current_user.id)
    return render_template('food_log/index.html',
                           today_logs=today_logs,
                           today_totals=today_totals)


@food_log_bp.route('/search')
@login_required
def search():
    """AJAX endpoint — search USDA food database."""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    results = search_usda(query)
    return jsonify(results)


@food_log_bp.route('/delete/<int:log_id>', methods=['POST'])
@login_required
def delete(log_id):
    log = FoodLog.query.filter_by(id=log_id, user_id=current_user.id).first_or_404()
    name = log.food_name
    db.session.delete(log)
    db.session.commit()
    flash(f'Removed {name} from your log.', 'info')
    return redirect(url_for('food_log.index'))


@food_log_bp.route('/history')
@login_required
def history():
    """Past 7 days of logs grouped by date."""
    from collections import defaultdict
    logs = FoodLog.query.filter_by(user_id=current_user.id)\
                        .order_by(FoodLog.logged_at.desc())\
                        .limit(100).all()

    grouped = defaultdict(list)
    for log in logs:
        grouped[log.logged_at.date()].append(log)

    return render_template('food_log/history.html', grouped=dict(grouped))
