"""
gamification.py — Central gamification engine for The Healthy Plate Quest.

This service is the single source of truth for all reward logic.
Call its functions after any user action (logging a meal, completing a quest, etc.)
and it will handle XP, badge checks, streak updates, and leaderboard sync automatically.
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
    'log_meal_complete':     20,   # All macros filled in
    'complete_quest_easy':   30,
    'complete_quest_medium': 60,
    'complete_quest_hard':   100,
    'streak_milestone_3':    25,
    'streak_milestone_7':    75,
    'streak_milestone_30':   300,
    'first_meal_today':      5,    # Bonus for logging first meal of the day
    'onboarding':            50,
    'level_up_bonus':        50,   # Bonus awarded on level-up
}

DIFFICULTY_XP = {
    'easy':   XP_EVENTS['complete_quest_easy'],
    'medium': XP_EVENTS['complete_quest_medium'],
    'hard':   XP_EVENTS['complete_quest_hard'],
}


# ─────────────────────────────────────────────
#  MAIN AWARD FUNCTION
# ─────────────────────────────────────────────

def award_xp(user, amount, reason='', update_leaderboard=True):
    """
    Award XP to a user, trigger level-up logic, and sync the leaderboard.
    Returns a dict with keys: xp_awarded, leveled_up, new_level, new_badges.
    """
    old_level = user.level
    leveled_up = user.add_xp(amount, reason)   # commits internally
    new_badges = []

    if leveled_up:
        # Bonus XP for leveling up (does not re-trigger level-up recursively)
        user.xp_points += XP_EVENTS['level_up_bonus']
        db.session.commit()
        # Check level-based badges
        new_badges += check_and_award_badges(user, trigger_type='level_reached',
                                              trigger_value=user.level)

    if update_leaderboard:
        LeaderboardEntry.upsert_entry(user.id, xp_delta=amount)

    return {
        'xp_awarded': amount,
        'leveled_up': leveled_up,
        'old_level': old_level,
        'new_level': user.level,
        'new_badges': new_badges,
    }


# ─────────────────────────────────────────────
#  STREAK MANAGEMENT
# ─────────────────────────────────────────────

def process_streak(user):
    """
    Update the user's streak and award milestone XP/badges if earned.
    Returns a dict describing what happened.
    """
    result = {'streak_updated': False, 'streak_broken': False,
              'milestone': None, 'xp_awarded': 0, 'new_badges': []}

    today = date.today()
    if user.last_log_date == today:
        return result  # Already processed today

    previously_broken = (
        user.last_log_date is not None
        and (today - user.last_log_date).days > 1
    )

    user.update_streak()  # Updates current_streak, longest_streak, last_log_date
    result['streak_updated'] = True
    result['streak_broken'] = previously_broken

    new_streak = user.current_streak

    # Milestone XP rewards
    milestones = {3: 'streak_milestone_3', 7: 'streak_milestone_7',
                  30: 'streak_milestone_30'}
    if new_streak in milestones:
        xp = XP_EVENTS[milestones[new_streak]]
        award_xp(user, xp, reason=f'{new_streak}-day streak milestone')
        result['milestone'] = new_streak
        result['xp_awarded'] = xp

    # Streak-based badges
    result['new_badges'] += check_and_award_badges(
        user, trigger_type='streak_days', trigger_value=new_streak
    )

    return result


# ─────────────────────────────────────────────
#  BADGE CHECKING
# ─────────────────────────────────────────────

def check_and_award_badges(user, trigger_type, trigger_value):
    """
    Check all badges with the given trigger_type and award any the user
    qualifies for but hasn't received yet.
    Returns list of newly awarded Badge objects.
    """
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
    """
    Run the full badge check suite for a user after a significant action.
    Checks all trigger types based on current user stats.
    Returns all newly awarded badges.
    """
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
#  QUEST ENGINE
# ─────────────────────────────────────────────

def assign_daily_quests(user, force=False):
    """
    Assign today's daily quests to a user if they don't already have them.
    Call this on dashboard load or first login of the day.
    Returns list of newly assigned UserQuest objects.
    """
    from app.models.quest import Quest, UserQuest

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today_start + timedelta(days=1)

    # Check if already assigned today
    existing = UserQuest.query.filter(
        UserQuest.user_id == user.id,
        UserQuest.assigned_at >= today_start,
    ).first()

    if existing and not force:
        return []

    # Pick up to 3 active daily quests not already in progress
    active_quest_ids = {
        uq.quest_id for uq in UserQuest.query.filter_by(
            user_id=user.id, is_completed=False
        ).all()
    }
    daily_quests = Quest.query.filter(
        Quest.quest_type == 'daily',
        Quest.is_active == True,
        ~Quest.id.in_(active_quest_ids) if active_quest_ids else True,
    ).limit(3).all()

    new_assignments = []
    for quest in daily_quests:
        uq = UserQuest(
            user_id=user.id,
            quest_id=quest.id,
            expires_at=tomorrow,
        )
        db.session.add(uq)
        new_assignments.append(uq)

    if new_assignments:
        db.session.commit()

    return new_assignments


def assign_weekly_quests(user):
    """
    Assign this week's weekly quests to a user if not already assigned.
    Returns list of newly assigned UserQuest objects.
    """
    from app.models.quest import Quest, UserQuest

    # Week window: Monday 00:00 → next Monday 00:00
    today = datetime.utcnow()
    week_start = today - timedelta(days=today.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)

    existing = UserQuest.query.filter(
        UserQuest.user_id == user.id,
        UserQuest.assigned_at >= week_start,
        UserQuest.quest.has(quest_type='weekly'),
    ).first()

    if existing:
        return []

    active_quest_ids = {
        uq.quest_id for uq in UserQuest.query.filter_by(
            user_id=user.id, is_completed=False
        ).all()
    }
    weekly_quests = Quest.query.filter(
        Quest.quest_type == 'weekly',
        Quest.is_active == True,
        ~Quest.id.in_(active_quest_ids) if active_quest_ids else True,
    ).limit(2).all()

    new_assignments = []
    for quest in weekly_quests:
        uq = UserQuest(
            user_id=user.id,
            quest_id=quest.id,
            expires_at=week_end,
        )
        db.session.add(uq)
        new_assignments.append(uq)

    if new_assignments:
        db.session.commit()

    return new_assignments


def complete_quest(user, user_quest):
    """
    Mark a UserQuest as complete, award XP, update leaderboard, check badges.
    Returns result dict with xp_awarded, new_badges, leveled_up.
    """
    if user_quest.is_completed or user_quest.xp_claimed:
        return {'xp_awarded': 0, 'new_badges': [], 'leveled_up': False}

    quest = user_quest.quest
    xp = DIFFICULTY_XP.get(quest.difficulty, 50)

    user_quest.is_completed = True
    user_quest.completed_at = datetime.utcnow()
    user_quest.xp_claimed = True
    user.total_quests_completed += 1
    db.session.commit()

    # Award XP
    result = award_xp(user, xp, reason=f'Completed quest: {quest.title}')

    # Leaderboard quest count
    LeaderboardEntry.upsert_entry(user.id, quests_delta=1)

    # Badge check for quest milestones
    result['new_badges'] += check_and_award_badges(
        user, 'quests_completed', user.total_quests_completed
    )

    # Badge tied directly to this quest
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
    """
    Scan the user's active quests for any matching criteria_type and
    increment their progress. Auto-complete quests that hit their target.

    Returns list of result dicts from complete_quest() for any completed quests.
    """
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
                result['quest_icon'] = uq.quest.icon
                completion_results.append(result)

    return completion_results


# ─────────────────────────────────────────────
#  NOTIFICATION BUILDER
# ─────────────────────────────────────────────

def build_reward_summary(xp_result=None, streak_result=None, quest_results=None):
    """
    Build a human-readable list of reward messages to flash to the user.
    Pass any combination of results from award_xp / process_streak / update_quest_progress.
    Returns list of (category, message) tuples compatible with Flask flash().
    """
    messages = []

    if xp_result and xp_result.get('xp_awarded', 0) > 0:
        messages.append(('success', f"⭐ +{xp_result['xp_awarded']} XP earned!"))
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
            icon = qr.get('quest_icon', '⚔️')
            title = qr.get('quest_title', 'Quest')
            messages.append(('success',
                f"{icon} Quest complete: <strong>{title}</strong>! +{qr['xp_awarded']} XP"))
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
            f"{badge.icon} New badge unlocked: <strong>{badge.name}</strong>!"))

    return messages
