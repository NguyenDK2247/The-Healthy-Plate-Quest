"""
personalization.py — Dynamic personalization engine for The Healthy Plate Quest.

Moves the system from static onboarding-based personalization toward a 
continuously updated profile driven by actual user behavior.

How it works:
  - Analyses the user's food log history using rule-based logic
  - Detects implicit food preferences, nutritional patterns, and engagement behavior
  - Updates user profile fields periodically (every 5 meals logged)
  - Produces a personalizationProfile used to enrich AI coaching context

Triggered automatically from food_log.py after every 5th meal logged.
Can also be called manually via flask shell: update_user_profile(user)
"""

from collections import Counter
from datetime import date, timedelta
from app import db
from app.models.food_log import FoodLog


# ─────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────

# How often to re-run the personalization update (every N meals)
UPDATE_EVERY_N_MEALS = 5

# How many days of history to analyse
ANALYSIS_WINDOW_DAYS = 14

# Thresholds for nutritional pattern detection
PROTEIN_TARGET_PER_MEAL = 20      # grams — below this = low protein per meal
FIBER_TARGET_DAILY      = 25      # grams — below this = low fiber day
CALORIE_TARGET_DAILY    = 2000    # kcal — reference point for over/under eating
VEGETABLE_TARGET_WEEKLY = 10      # servings — below this = low veg intake


# ─────────────────────────────────────────────
#  ENGAGEMENT TIER DETECTION
# ─────────────────────────────────────────────

def get_engagement_tier(user):
    """
    Categorize user into low / medium / high engagement
    based on recent activity. Used by both personalization
    and adaptive gamification (Point 2).

    Returns: 'low', 'medium', or 'high'
    """
    today    = date.today()
    week_ago = today - timedelta(days=7)

    recent_logs = FoodLog.query.filter(
        FoodLog.user_id == user.id,
        db.func.date(FoodLog.logged_at) >= week_ago,
    ).all()

    days_logged_this_week = len({log.logged_at.date() for log in recent_logs})
    meals_this_week       = len(recent_logs)
    streak                = user.current_streak or 0

    # High: active 5+ days this week OR streak > 5
    if days_logged_this_week >= 5 or streak > 5:
        return 'high'
    # Low: logged on 0–1 days this week AND streak < 2
    elif days_logged_this_week <= 1 and streak < 2:
        return 'low'
    # Medium: everything in between
    else:
        return 'medium'


# ─────────────────────────────────────────────
#  BEHAVIORAL ANALYSIS
# ─────────────────────────────────────────────

def analyse_food_history(user):
    """
    Analyse the user's recent food log to extract implicit preferences
    and nutritional patterns.

    Returns a dict with keys:
      - top_foods           : list of most frequently logged food names
      - top_categories      : list of most logged food categories
      - implicit_ingredients: inferred favourite ingredients from logs
      - avg_daily_calories  : average calories per logged day
      - avg_daily_protein   : average protein per logged day
      - avg_daily_fiber     : average fiber per logged day
      - low_protein         : bool — consistently low protein intake
      - low_fiber           : bool — consistently low fiber intake
      - low_vegetables      : bool — not logging enough vegetables
      - skips_breakfast     : bool — rarely logs breakfast
      - engagement_tier     : 'low', 'medium', or 'high'
      - days_analysed       : number of days with data in window
    """
    today      = date.today()
    window_ago = today - timedelta(days=ANALYSIS_WINDOW_DAYS)

    logs = FoodLog.query.filter(
        FoodLog.user_id == user.id,
        db.func.date(FoodLog.logged_at) >= window_ago,
    ).all()

    if not logs:
        return None

    # Unique days logged
    days_with_data = {log.logged_at.date() for log in logs}
    n_days = max(len(days_with_data), 1)

    # Most frequently logged food names (top 5)
    food_counts = Counter(log.food_name.lower() for log in logs)
    top_foods   = [name for name, _ in food_counts.most_common(5)]

    # Most logged categories
    cat_counts    = Counter(log.food_category for log in logs if log.food_category)
    top_categories = [cat for cat, _ in cat_counts.most_common(3)]

    # Infer implicit ingredient preferences from food names
    # Extract meaningful words (3+ chars, not common stop words)
    stop_words = {'with', 'and', 'the', 'for', 'low', 'fat', 'high', 'free',
                  'whole', 'grain', 'fresh', 'organic', 'natural', 'raw'}
    ingredient_words = []
    for food_name in top_foods:
        words = food_name.replace(',', ' ').replace('-', ' ').split()
        ingredient_words += [w for w in words if len(w) >= 3 and w not in stop_words]
    implicit_ingredients = list(dict.fromkeys(ingredient_words))[:8]  # deduplicated, max 8

    # Daily nutrition averages
    total_calories = sum(log.calories or 0 for log in logs)
    total_protein  = sum(log.protein_g or 0 for log in logs)
    total_fiber    = sum(log.fiber_g or 0 for log in logs)

    avg_daily_calories = round(total_calories / n_days, 1)
    avg_daily_protein  = round(total_protein  / n_days, 1)
    avg_daily_fiber    = round(total_fiber    / n_days, 1)

    # Pattern flags
    avg_protein_per_meal = (total_protein / len(logs)) if logs else 0
    low_protein = avg_protein_per_meal < PROTEIN_TARGET_PER_MEAL

    low_fiber = avg_daily_fiber < FIBER_TARGET_DAILY

    veg_logs = [l for l in logs if l.food_category == 'vegetable']
    veg_per_week = (len(veg_logs) / n_days) * 7
    low_vegetables = veg_per_week < VEGETABLE_TARGET_WEEKLY

    breakfast_logs = [l for l in logs if l.meal_type == 'breakfast']
    skips_breakfast = (len(breakfast_logs) / n_days) < 0.4  # logs breakfast <40% of days

    return {
        'top_foods':            top_foods,
        'top_categories':       top_categories,
        'implicit_ingredients': implicit_ingredients,
        'avg_daily_calories':   avg_daily_calories,
        'avg_daily_protein':    avg_daily_protein,
        'avg_daily_fiber':      avg_daily_fiber,
        'low_protein':          low_protein,
        'low_fiber':            low_fiber,
        'low_vegetables':       low_vegetables,
        'skips_breakfast':      skips_breakfast,
        'engagement_tier':      get_engagement_tier(user),
        'days_analysed':        n_days,
    }


# ─────────────────────────────────────────────
#  PROFILE UPDATER
# ─────────────────────────────────────────────

def update_user_profile(user):
    """
    Run the behavioral analysis and update the user's profile fields
    based on what they've actually been eating.

    Updates:
      - favorite_ingredients  : merged with implicit ingredients from logs
      - nutrition_goal        : may be reinforced or surfaced in AI context
                                (never overrides user's explicit choice)

    Returns the analysis dict so it can be passed to the AI coach.
    """
    analysis = analyse_food_history(user)
    if not analysis:
        return None

    # Merge implicit ingredients into favourite_ingredients
    # User's explicit choices take priority — we only ADD new ones, never remove
    existing_favs = [
        f.strip().lower()
        for f in (user.favorite_ingredients or '').split(',')
        if f.strip()
    ]
    new_ingredients = [
        ing for ing in analysis['implicit_ingredients']
        if ing.lower() not in existing_favs
    ]

    # Add up to 3 new inferred ingredients, keeping total under 15
    combined = existing_favs + new_ingredients[:3]
    combined = combined[:15]  # cap total

    if combined != existing_favs:
        user.favorite_ingredients = ', '.join(combined)
        db.session.commit()

    return analysis


def should_update_profile(user):
    """
    Returns True if it's time to run a profile update.
    Updates every UPDATE_EVERY_N_MEALS meals logged.
    """
    total = user.total_meals_logged or 0
    return total > 0 and total % UPDATE_EVERY_N_MEALS == 0


# ─────────────────────────────────────────────
#  RICH CONTEXT BUILDER FOR AI COACH
# ─────────────────────────────────────────────

def build_dynamic_context(user):
    """
    Build a rich, behavior-informed context string to inject into
    the Coach Vita system prompt, replacing the simple static profile.

    Returns a string ready to be included in the system prompt.
    """
    analysis = analyse_food_history(user)
    if not analysis:
        return ''

    lines = ['\nDynamic user insights (derived from recent behavior):']

    tier = analysis['engagement_tier']
    lines.append(f'- Engagement level: {tier} ({"very active" if tier == "high" else ("building habit" if tier == "medium" else "needs encouragement")})')

    if analysis['top_foods']:
        lines.append(f'- Most frequently logged foods: {", ".join(analysis["top_foods"])}')

    if analysis['top_categories']:
        lines.append(f'- Most logged food categories: {", ".join(analysis["top_categories"])}')

    lines.append(f'- Average daily calories: {analysis["avg_daily_calories"]:.0f} kcal')
    lines.append(f'- Average daily protein: {analysis["avg_daily_protein"]:.1f}g')
    lines.append(f'- Average daily fiber: {analysis["avg_daily_fiber"]:.1f}g')

    # Coaching flags
    if analysis['low_protein']:
        lines.append('- Pattern detected: consistently low protein intake — gently encourage more protein-rich foods')
    if analysis['low_fiber']:
        lines.append('- Pattern detected: low fiber intake — suggest more vegetables, legumes, or whole grains')
    if analysis['low_vegetables']:
        lines.append('- Pattern detected: low vegetable variety — encourage adding more vegetables')
    if analysis['skips_breakfast']:
        lines.append('- Pattern detected: often skips breakfast — if relevant, mention the benefits of morning meals')

    lines.append(f'- Data based on last {analysis["days_analysed"]} days of logging.')

    return '\n'.join(lines)
