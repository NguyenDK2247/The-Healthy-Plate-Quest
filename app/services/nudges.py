"""
nudges.py — Behavioral science nudge engine for The Healthy Plate Quest.

Based on:
    - BJ Fogg's Behavior Model (Motivation × Ability × Prompt)
    - Self-Determination Theory (Autonomy, Competence, Relatedness)
    - Variable reward schedules (Skinner)
    - Loss aversion (Kahneman & Tversky)

Call generate_nudges(user) from the dashboard route to get
a list of contextual nudge dicts to display to the user.
"""

from datetime import date, datetime, timedelta
from app.models.food_log import FoodLog


# ─────────────────────────────────────────────
#  NUDGE TYPES
#
#  Each nudge is a dict:
#  {
#    'type':    str  — category for styling (streak, loss, social, tip, reward)
#    'icon':    str  — emoji
#    'title':   str  — short headline
#    'message': str  — 1-2 sentence body
#    'action':  str  — optional CTA label
#    'url':     str  — optional CTA link (passed as url_for key)
#    'priority': int — higher = shown first (1–10)
#  }
# ─────────────────────────────────────────────

def generate_nudges(user, today_totals=None):
    """
    Generate a prioritized list of contextual nudges for the current user.
    Returns up to 3 nudges, sorted by priority descending.
    """
    nudges = []
    today  = date.today()

    # Fallback if totals not provided
    if today_totals is None:
        today_totals = FoodLog.get_today_totals(user.id)

    meals_today   = today_totals.get('meal_count', 0)
    calories_today = today_totals.get('calories', 0)
    streak        = user.current_streak or 0
    last_log      = user.last_log_date

    # ── 1. LOSS AVERSION — streak at risk ─────────────────────────────────
    # Most powerful nudge: streak about to be lost
    if streak >= 2 and last_log and last_log < today and meals_today == 0:
        nudges.append({
            'type':     'loss',
            'icon':     '🔥',
            'title':    f'Your {streak}-day streak is at risk!',
            'message':  "Log at least one meal today to keep your streak alive. Don't let it slip away!",
            'action':   'Log a meal now',
            'url':      'food_log.index',
            'priority': 10,
        })

    # ── 2. STREAK MILESTONE — approaching a milestone ─────────────────────
    milestones = [3, 7, 14, 30, 60, 100]
    for ms in milestones:
        if streak == ms - 1 and meals_today == 0:
            nudges.append({
                'type':     'streak',
                'icon':     '⚡',
                'title':    f'One day away from a {ms}-day streak!',
                'message':  f'Log a meal today and hit your {ms}-day milestone for a big XP bonus!',
                'action':   'Log a meal',
                'url':      'food_log.index',
                'priority': 9,
            })
            break

    # ── 3. FRESH START — first meal of the day ────────────────────────────
    if meals_today == 0:
        hour = datetime.now().hour
        if hour < 11:
            nudges.append({
                'type':     'tip',
                'icon':     '🌅',
                'title':    'Good morning! Start strong.',
                'message':  'Logging breakfast is linked to better food choices all day. What are you having?',
                'action':   'Log breakfast',
                'url':      'food_log.index',
                'priority': 7,
            })
        elif hour < 15:
            nudges.append({
                'type':     'tip',
                'icon':     '☀️',
                'title':    "You haven't logged anything yet today.",
                'message':  "Even logging just one meal earns you XP and keeps your streak alive. Take 30 seconds!",
                'action':   'Log a meal',
                'url':      'food_log.index',
                'priority': 7,
            })
        else:
            nudges.append({
                'type':     'loss',
                'icon':     '🌙',
                'title':    "Don't forget to log today!",
                'message':  "The day isn't over yet — log your meals before midnight to protect your streak.",
                'action':   'Log now',
                'url':      'food_log.index',
                'priority': 8,
            })

    # ── 4. VARIABLE REWARD — surprise bonus nudge ─────────────────────────
    # Shown randomly ~30% of the time to create anticipation (Skinner schedule)
    import random
    random.seed(str(user.id) + str(today))  # deterministic per user per day
    if random.random() < 0.30 and meals_today >= 1:
        nudges.append({
            'type':     'reward',
            'icon':     '🎁',
            'title':    'Surprise bonus available today!',
            'message':  'Complete one more quest today for a chance at a mystery XP bonus. Check the quest board!',
            'action':   'View quests',
            'url':      'quests.index',
            'priority': 6,
        })

    # ── 5. NUTRITION TIP — goal-specific advice ───────────────────────────
    if meals_today >= 1:
        protein = today_totals.get('protein_g', 0)
        fiber   = today_totals.get('fiber_g', 0)
        goal    = user.nutrition_goal or 'general'

        if goal == 'muscle_building' and protein < 30:
            nudges.append({
                'type':     'tip',
                'icon':     '💪',
                'title':    'Protein intake is looking low.',
                'message':  f"You've had {protein:.0f}g of protein so far. Aim for 50g+ today to support muscle building.",
                'action':   None,
                'url':      None,
                'priority': 5,
            })
        elif goal == 'gut_health' and fiber < 10:
            nudges.append({
                'type':     'tip',
                'icon':     '🌿',
                'title':    'Boost your fiber today.',
                'message':  f"Only {fiber:.0f}g of fiber so far. Add some legumes, oats or vegetables to support your gut health goal.",
                'action':   'Ask Coach Vita',
                'url':      'coach.index',
                'priority': 5,
            })
        elif goal == 'energy' and calories_today < 600 and meals_today <= 1:
            nudges.append({
                'type':     'tip',
                'icon':     '⚡',
                'title':    'Your energy levels need fuel.',
                'message':  "You've eaten quite little so far. Regular meals keep energy stable throughout the day.",
                'action':   'Get meal ideas',
                'url':      'coach.index',
                'priority': 5,
            })
        else:
            # Generic positive reinforcement
            nudges.append({
                'type':     'tip',
                'icon':     '🌈',
                'title':    'Try eating the rainbow today!',
                'message':  'Aim for 5 different colored foods — it unlocks the Rainbow Plate quest and earns bonus XP.',
                'action':   'View quests',
                'url':      'quests.index',
                'priority': 3,
            })

    # ── 6. SOCIAL PROOF — leaderboard motivation ─────────────────────────
    if user.total_meals_logged >= 5:
        nudges.append({
            'type':     'social',
            'icon':     '🏆',
            'title':    'Check the weekly leaderboard!',
            'message':  'See how you rank against other players this week. Every meal logged earns you leaderboard XP.',
            'action':   'View leaderboard',
            'url':      'leaderboard.index',
            'priority': 2,
        })

    # ── 7. COMPETENCE BOOST — celebrate progress ─────────────────────────
    if streak >= 7:
        nudges.append({
            'type':     'streak',
            'icon':     '🔥',
            'title':    f'{streak}-day streak — incredible!',
            'message':  "You're building a real habit. Research shows that 7+ day streaks are a strong predictor of long-term behavior change. Keep it up!",
            'action':   None,
            'url':      None,
            'priority': 4,
        })

    # ── 8. AUTONOMY SUPPORT — weekly goal setting ─────────────────────────
    # Shown on Mondays to encourage weekly intention setting
    if today.weekday() == 0 and meals_today == 0:
        nudges.append({
            'type':     'tip',
            'icon':     '🎯',
            'title':    "It's Monday — set your week up for success!",
            'message':  'Check your active quests and ask Coach Vita to generate a personalized challenge just for you.',
            'action':   'Talk to Coach Vita',
            'url':      'coach.index',
            'priority': 6,
        })

    # Sort by priority and return top 3
    nudges.sort(key=lambda n: n['priority'], reverse=True)
    return nudges[:3]


# ─────────────────────────────────────────────
#  WEEKLY GOAL HELPERS
# ─────────────────────────────────────────────

def get_weekly_summary(user):
    """
    Returns a summary dict of the user's activity over the past 7 days.
    Used on the dashboard for the weekly progress card.
    """
    from app.models.food_log import FoodLog
    from app import db

    today     = date.today()
    week_ago  = today - timedelta(days=6)

    logs = FoodLog.query.filter(
        FoodLog.user_id == user.id,
        db.func.date(FoodLog.logged_at) >= week_ago,
    ).all()

    days_logged = len({log.logged_at.date() for log in logs})
    total_meals = len(logs)
    avg_calories = (sum(l.calories for l in logs) / total_meals) if total_meals else 0
    avg_protein  = (sum(l.protein_g for l in logs) / total_meals) if total_meals else 0

    # Build a 7-day activity grid (True/False per day)
    activity_grid = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        logged = any(log.logged_at.date() == d for log in logs)
        activity_grid.append({'date': d, 'logged': logged, 'label': d.strftime('%a')})

    return {
        'days_logged':   days_logged,
        'total_meals':   total_meals,
        'avg_calories':  round(avg_calories, 0),
        'avg_protein':   round(avg_protein, 1),
        'activity_grid': activity_grid,
        'completion_pct': round((days_logged / 7) * 100),
    }
