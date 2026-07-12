"""
gamification.py — Central gamification engine for The Healthy Plate Quest.

This service is the single source of truth for all reward logic.
Call its functions after any user action (logging a meal, completing a quest, etc.)
and it will handle XP, badge checks, streak updates, and leaderboard sync automatically.

Adaptive Gamification:
  - get_engagement_tier() classifies users as low/medium/high
  - get_xp_multiplier() adjusts XP rewards based on engagement tier
  - assign_daily_quests() now filters quests by difficulty based on tier
  - assign_weekly_quests() does the same for weekly quests
"""

from datetime import datetime, date, timedelta
from app import db
from app.models.badge import Badge, UserBadge
from app.models.leaderboard import LeaderboardEntry


# ─────────────────────────────────────────────
#  XP AWARD TABLE
# ─────────────────────────────────────────────

XP_EVENTS = {
    'log_meal':              10,
    'log_meal_complete':     20,
    'complete_quest_easy':   30,
    'complete_quest_medium': 60,
    'complete_quest_hard':   100,
    'streak_milestone_3':    25,
    'streak_milestone_7':    75,
    'streak_milestone_30':   300,
    'first_meal_today':      5,
    'onboarding':            50,
    'level_up_bonus':        50,
}

DIFFICULTY_XP = {
    'easy':   XP_EVENTS['complete_quest_easy'],
    'medium': XP_EVENTS['complete_quest_medium'],
    'hard':   XP_EVENTS['complete_quest_hard'],
}


# ─────────────────────────────────────────────
#  ADAPTIVE GAMIFICATION (Feedback Point 2)
# ─────────────────────────────────────────────

# XP multipliers per engagement tier
# Low users get a boost to encourage participation
# High users get standard rewards — they're already engaged
XP_MULTIPLIERS = {
    'low':    1.5,   # +50% XP to encourage low-engagement users
    'medium': 1.0,   # Standard
    'high':   1.0,   # Standard — challenge is the reward for high users
}

# Which quest difficulties to assign per engagement tier
# Low users get easier quests to build confidence
# High users get harder quests to stay challenged
QUEST_DIFFICULTY_MAP = {
    'low':    ['easy'],
    'medium': ['easy', 'medium'],
    'high':   ['medium', 'hard'],
}


def get_engagement_tier(user):
    """
    Classify the user into low / medium / high engagement
    based on their activity over the past 7 days.

    Criteria:
      high   — logged on 5+ days this week OR current streak > 5
      low    — logged on 0–1 days this week AND streak < 2
      medium — everything in between

    Returns: 'low', 'medium', or 'high'
    """
    from app.models.food_log import FoodLog

    today    = date.today()
    week_ago = today - timedelta(days=7)

    recent_logs = FoodLog.query.filter(
        FoodLog.user_id == user.id,
        db.func.date(FoodLog.logged_at) >= week_ago,
    ).all()

    days_logged = len({log.logged_at.date() for log in recent_logs})
    streak      = user.current_streak or 0

    if days_logged >= 5 or streak > 5:
        return 'high'
    elif days_logged <= 1 and streak < 2:
        return 'low'
    else:
        return 'medium'


def get_xp_multiplier(user):
    """
    Return the XP multiplier for this user based on their engagement tier.
    Low-engagement users receive a 1.5x boost to encourage participation.
    """
    tier = get_engagement_tier(user)
    return XP_MULTIPLIERS.get(tier, 1.0)


def get_adapted_xp(user, base_amount):
    """
    Apply the engagement-tier multiplier to a base XP amount.
    Always rounds to nearest integer.
    """
    multiplier = get_xp_multiplier(user)
    return max(1, round(base_amount * multiplier))


# ─────────────────────────────────────────────
#  MAIN AWARD FUNCTION
# ─────────────────────────────────────────────

def award_xp(user, amount, reason='', update_leaderboard=True):
    """
    Award XP to a user, trigger level-up logic, and sync the leaderboard.
    Applies adaptive XP multiplier based on engagement tier.
    Returns a dict with keys: xp_awarded, leveled_up, new_level, new_badges.
    """
    # Apply adaptive multiplier
    adapted_amount = get_adapted_xp(user, amount)

    old_level  = user.level
    leveled_up = user.add_xp(adapted_amount, reason)
    new_badges = []

    if leveled_up:
        user.xp_points += XP_EVENTS['level_up_bonus']
        db.session.commit()
        new_badges += check_and_award_badges(user, trigger_type='level_reached',
                                              trigger_value=user.level)

    if update_leaderboard:
        LeaderboardEntry.upsert_entry(user.id, xp_delta=adapted_amount)

    return {
        'xp_awarded':   adapted_amount,
        'base_amount':  amount,
        'multiplier':   get_xp_multiplier(user),
        'leveled_up':   leveled_up,
        'old_level':    old_level,
        'new_level':    user.level,
        'new_badges':   new_badges,
    }


# ─────────────────────────────────────────────
#  STREAK MANAGEMENT
# ─────────────────────────────────────────────

def process_streak(user):
    result = {'streak_updated': False, 'streak_broken': False,
              'milestone': None, 'xp_awarded': 0, 'new_badges': []}

    today = date.today()
    if user.last_log_date == today:
        return result

    previously_broken = (
        user.last_log_date is not None
        and (today - user.last_log_date).days > 1
    )

    user.update_streak()
    result['streak_updated'] = True
    result['streak_broken']  = previously_broken
    new_streak = user.current_streak

    milestones = {3: 'streak_milestone_3', 7: 'streak_milestone_7',
                  30: 'streak_milestone_30'}
    if new_streak in milestones:
        xp = XP_EVENTS[milestones[new_streak]]
        award_xp(user, xp, reason=f'{new_streak}-day streak milestone')
        result['milestone']   = new_streak
        result['xp_awarded']  = xp

    result['new_badges'] += check_and_award_badges(
        user, trigger_type='streak_days', trigger_value=new_streak
    )
    return result


# ─────────────────────────────────────────────
#  BADGE CHECKING
# ─────────────────────────────────────────────

def check_and_award_badges(user, trigger_type, trigger_value):
    already_earned_ids = {ub.badge_id for ub in user.badges.all()}
    candidates = Badge.query.filter(
        Badge.trigger_type == trigger_type,
        Badge.trigger_value <= trigger_value,
        ~Badge.id.in_(already_earned_ids) if already_earned_ids else True,
    ).all()

    new_badges = []
    for badge in candidates:
        ub = UserBadge(user_id=user.id, badge_id=badge.id)
        db.session.add(ub)
        new_badges.append(badge)

    if new_badges:
        db.session.commit()
    return new_badges


def run_all_badge_checks(user):
    new_badges = []
    checks = [
        ('meals_logged',     user.total_meals_logged),
        ('streak_days',      user.current_streak),
        ('quests_completed', user.total_quests_completed),
        ('level_reached',    user.level),
    ]
    for trigger_type, value in checks:
        new_badges += check_and_award_badges(user, trigger_type, value)
    return new_badges


# ─────────────────────────────────────────────
#  QUEST ENGINE (Adaptive)
# ─────────────────────────────────────────────

def assign_daily_quests(user, force=False):
    """
    Assign today's daily quests filtered by the user's engagement tier.
    Low users get easy quests; high users get medium/hard quests.
    """
    from app.models.quest import Quest, UserQuest

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow    = today_start + timedelta(days=1)
    now         = datetime.utcnow()

    # Check if already assigned fresh daily quests today
    existing_today = UserQuest.query.filter(
        UserQuest.user_id == user.id,
        UserQuest.assigned_at >= today_start,
        UserQuest.is_completed == False,
    ).join(UserQuest.quest).filter(
        Quest.quest_type == 'daily'
    ).first()

    if existing_today and not force:
        return []

    # Only exclude currently active unexpired quests
    active_quest_ids = {
        uq.quest_id for uq in UserQuest.query.filter(
            UserQuest.user_id == user.id,
            UserQuest.is_completed == False,
            db.or_(UserQuest.expires_at == None, UserQuest.expires_at > now)
        ).all()
    }

    # Adaptive: filter by appropriate difficulty for this user's tier
    tier       = get_engagement_tier(user)
    difficulty = QUEST_DIFFICULTY_MAP.get(tier, ['easy', 'medium'])

    daily_quests = Quest.query.filter(
        Quest.quest_type == 'daily',
        Quest.is_active  == True,
        Quest.difficulty.in_(difficulty),
        ~Quest.id.in_(active_quest_ids) if active_quest_ids else True,
    ).limit(3).all()

    # Fallback: if no quests match the difficulty filter, show any available
    if not daily_quests:
        daily_quests = Quest.query.filter(
            Quest.quest_type == 'daily',
            Quest.is_active  == True,
            ~Quest.id.in_(active_quest_ids) if active_quest_ids else True,
        ).limit(3).all()

    new_assignments = []
    for quest in daily_quests:
        uq = UserQuest(
            user_id    = user.id,
            quest_id   = quest.id,
            expires_at = tomorrow,
        )
        db.session.add(uq)
        new_assignments.append(uq)

    if new_assignments:
        db.session.commit()
    return new_assignments


def assign_weekly_quests(user):
    """
    Assign weekly quests filtered by the user's engagement tier.
    """
    from app.models.quest import Quest, UserQuest

    today      = datetime.utcnow()
    week_start = today - timedelta(days=today.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end   = week_start + timedelta(days=7)
    now        = datetime.utcnow()

    existing = UserQuest.query.filter(
        UserQuest.user_id    == user.id,
        UserQuest.assigned_at >= week_start,
        UserQuest.quest.has(quest_type='weekly'),
    ).first()

    if existing:
        return []

    active_quest_ids = {
        uq.quest_id for uq in UserQuest.query.filter(
            UserQuest.user_id == user.id,
            UserQuest.is_completed == False,
            db.or_(UserQuest.expires_at == None, UserQuest.expires_at > now)
        ).all()
    }

    # Adaptive difficulty filter
    tier       = get_engagement_tier(user)
    difficulty = QUEST_DIFFICULTY_MAP.get(tier, ['easy', 'medium'])

    weekly_quests = Quest.query.filter(
        Quest.quest_type == 'weekly',
        Quest.is_active  == True,
        Quest.difficulty.in_(difficulty),
        ~Quest.id.in_(active_quest_ids) if active_quest_ids else True,
    ).limit(2).all()

    # Fallback
    if not weekly_quests:
        weekly_quests = Quest.query.filter(
            Quest.quest_type == 'weekly',
            Quest.is_active  == True,
            ~Quest.id.in_(active_quest_ids) if active_quest_ids else True,
        ).limit(2).all()

    new_assignments = []
    for quest in weekly_quests:
        uq = UserQuest(
            user_id    = user.id,
            quest_id   = quest.id,
            expires_at = week_end,
        )
        db.session.add(uq)
        new_assignments.append(uq)

    if new_assignments:
        db.session.commit()
    return new_assignments


def complete_quest(user, user_quest):
    if user_quest.is_completed or user_quest.xp_claimed:
        return {'xp_awarded': 0, 'new_badges': [], 'leveled_up': False}

    quest = user_quest.quest
    xp    = DIFFICULTY_XP.get(quest.difficulty, 50)

    user_quest.is_completed = True
    user_quest.completed_at = datetime.utcnow()
    user_quest.xp_claimed   = True
    user.total_quests_completed += 1
    db.session.commit()

    result = award_xp(user, xp, reason=f'Completed quest: {quest.title}')
    LeaderboardEntry.upsert_entry(user.id, quests_delta=1)

    result['new_badges'] += check_and_award_badges(
        user, 'quests_completed', user.total_quests_completed
    )

    if quest.badge_reward_id:
        badge = Badge.query.get(quest.badge_reward_id)
        if badge:
            already = UserBadge.query.filter_by(
                user_id=user.id, badge_id=badge.id
            ).first()
            if not already:
                ub = UserBadge(user_id=user.id, badge_id=badge.id)
                db.session.add(ub)
                db.session.commit()
                result['new_badges'].append(badge)

    return result


def update_quest_progress(user, criteria_type, increment=1):
    from app.models.quest import UserQuest

    active = UserQuest.get_active_for_user(user.id)
    completion_results = []

    for uq in active:
        if uq.quest.criteria_type == criteria_type:
            uq.progress = min(uq.progress + increment, uq.quest.criteria_target)
            db.session.commit()
            if uq.progress >= uq.quest.criteria_target:
                result = complete_quest(user, uq)
                result['quest_title'] = uq.quest.title
                result['quest_icon']  = uq.quest.icon
                completion_results.append(result)

    return completion_results


# ─────────────────────────────────────────────
#  NOTIFICATION BUILDER
# ─────────────────────────────────────────────

def build_reward_summary(xp_result=None, streak_result=None, quest_results=None):
    messages = []

    if xp_result and xp_result.get('xp_awarded', 0) > 0:
        xp_msg = f"⭐ +{xp_result['xp_awarded']} XP earned!"
        # Show multiplier bonus if active
        if xp_result.get('multiplier', 1.0) > 1.0:
            xp_msg += f" (×{xp_result['multiplier']} engagement bonus!)"
        messages.append(('success', xp_msg))
        if xp_result.get('leveled_up'):
            messages.append(('warning',
                f"🎉 LEVEL UP! You're now Level {xp_result['new_level']}!"))

    if streak_result and streak_result.get('milestone'):
        messages.append(('info',
            f"🔥 {streak_result['milestone']}-day streak! +{streak_result['xp_awarded']} bonus XP!"))
    if streak_result and streak_result.get('streak_broken'):
        messages.append(('warning', '💔 Your streak was reset — start a new one today!'))

    if quest_results:
        for qr in quest_results:
            icon  = qr.get('quest_icon', '⚔️')
            title = qr.get('quest_title', 'Quest')
            messages.append(('success',
                f"{icon} Quest complete: {title} +{qr['xp_awarded']} XP"))
            if qr.get('leveled_up'):
                messages.append(('warning',
                    f"🎉 LEVEL UP! You're now Level {qr['new_level']}!"))

    all_badges = []
    if xp_result:
        all_badges += xp_result.get('new_badges', [])
    if streak_result:
        all_badges += streak_result.get('new_badges', [])
    if quest_results:
        for qr in quest_results:
            all_badges += qr.get('new_badges', [])

    for badge in all_badges:
        messages.append(('warning',
            f"{badge.icon} New badge unlocked: {badge.name}!"))

    return messages


# ─────────────────────────────────────────────
#  STREAK PROTECTION
# ─────────────────────────────────────────────

def check_streak_protection(user):
    today = date.today()
    if user.last_log_date is None:
        return False
    days_missed = (today - user.last_log_date).days
    return days_missed == 2


def apply_streak_shield(user):
    SHIELD_COST = 50
    if (user.xp_points or 0) < SHIELD_COST:
        return False
    user.xp_points    -= SHIELD_COST
    user.last_log_date = date.today() - timedelta(days=1)
    db.session.commit()
    return True
