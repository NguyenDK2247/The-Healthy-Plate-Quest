from flask import Blueprint, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.quest import Quest, UserQuest
from app.services.gamification import (
    assign_daily_quests, assign_weekly_quests,
    complete_quest, build_reward_summary
)

quests_bp = Blueprint('quests', __name__)


@quests_bp.route('/')
@login_required
def index():
    assign_daily_quests(current_user)
    assign_weekly_quests(current_user)

    now_active = UserQuest.get_active_for_user(current_user.id)
    daily   = [uq for uq in now_active if uq.quest.quest_type == 'daily']
    weekly  = [uq for uq in now_active if uq.quest.quest_type == 'weekly']
    special = [uq for uq in now_active if uq.quest.quest_type in ('special', 'ai_generated')]

    completed = UserQuest.query.filter_by(
        user_id=current_user.id, is_completed=True
    ).order_by(UserQuest.completed_at.desc()).limit(10).all()

    return render_template('quests/index.html',
                           daily=daily, weekly=weekly,
                           special=special, completed=completed)


@quests_bp.route('/claim/<int:uq_id>', methods=['POST'])
@login_required
def claim(uq_id):
    uq = UserQuest.query.filter_by(id=uq_id, user_id=current_user.id).first_or_404()
    if uq.xp_claimed:
        flash('Reward already claimed!', 'info')
    elif not uq.is_completed:
        flash("This quest isn't complete yet.", 'warning')
    else:
        result = complete_quest(current_user, uq)
        for cat, msg in build_reward_summary(xp_result=result):
            flash(msg, cat)
    return redirect(url_for('quests.index'))


@quests_bp.route('/browse')
@login_required
def browse():
    from datetime import datetime
    now = datetime.utcnow()

    # Only exclude quests that are currently active and unexpired
    # Expired daily quests from previous days should reappear as available
    active_quest_ids = {
        uq.quest_id for uq in UserQuest.query.filter(
            UserQuest.user_id == current_user.id,
            UserQuest.is_completed == False,
            db.or_(UserQuest.expires_at == None, UserQuest.expires_at > now)
        ).all()
    }

    available = Quest.query.filter(
        Quest.is_active == True,
        Quest.quest_type.in_(['daily', 'weekly', 'special']),
        ~Quest.id.in_(active_quest_ids) if active_quest_ids else True,
    ).all()

    return render_template('quests/browse.html', available=available)


@quests_bp.route('/accept/<int:quest_id>', methods=['POST'])
@login_required
def accept(quest_id):
    from datetime import datetime, timedelta
    quest = Quest.query.filter_by(id=quest_id, is_active=True).first_or_404()
    already = UserQuest.query.filter_by(user_id=current_user.id, quest_id=quest_id).first()
    if already:
        flash('You already have this quest!', 'info')
        return redirect(url_for('quests.browse'))

    expires = None
    if quest.quest_type == 'daily':
        expires = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    elif quest.quest_type == 'weekly':
        today = datetime.utcnow()
        days_to_monday = (7 - today.weekday()) % 7 or 7
        expires = today + timedelta(days=days_to_monday)

    uq = UserQuest(user_id=current_user.id, quest_id=quest_id, expires_at=expires)
    db.session.add(uq)
    db.session.commit()
    flash(f'Quest accepted: {quest.icon} {quest.title}', 'success')
    return redirect(url_for('quests.index'))


@quests_bp.route('/progress')
@login_required
def progress_api():
    active = UserQuest.get_active_for_user(current_user.id)
    data = [{'id': uq.id, 'title': uq.quest.title, 'icon': uq.quest.icon,
             'progress': uq.progress, 'target': uq.quest.criteria_target,
             'percent': uq.progress_percent(), 'xp_reward': uq.quest.xp_reward,
             'type': uq.quest.quest_type} for uq in active]
    return jsonify(data)
