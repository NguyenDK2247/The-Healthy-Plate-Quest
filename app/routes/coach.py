import json
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from flask_login import login_required, current_user
from app import db
from app.models.food_log import FoodLog
from app.models.quest import Quest, UserQuest
from app.services.ai_coach import chat_with_coach, generate_personalised_quest
from app.services.gamification import award_xp, build_reward_summary

coach_bp = Blueprint('coach', __name__)

HISTORY_SESSION_KEY = 'coach_conversation'


def get_recent_foods(user_id, limit=10):
    """Get list of recently logged food names for context."""
    logs = FoodLog.query.filter_by(user_id=user_id)\
                        .order_by(FoodLog.logged_at.desc())\
                        .limit(limit).all()
    return [log.food_name for log in logs]


@coach_bp.route('/')
@login_required
def index():
    today_totals = FoodLog.get_today_totals(current_user.id)
    history = session.get(HISTORY_SESSION_KEY, [])
    return render_template('coach/index.html',
                           today_totals=today_totals,
                           history=history)


@coach_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    """AJAX endpoint — sends a message to Coach Vita and returns the reply."""
    data = request.get_json()
    message = (data.get('message') or '').strip()

    if not message:
        return jsonify({'error': 'Empty message.'}), 400

    today_totals  = FoodLog.get_today_totals(current_user.id)
    recent_foods  = get_recent_foods(current_user.id)
    history       = session.get(HISTORY_SESSION_KEY, [])

    try:
        reply, updated_history = chat_with_coach(
            user=current_user,
            message=message,
            conversation_history=history,
            today_totals=today_totals,
            recent_foods=recent_foods,
        )
        session[HISTORY_SESSION_KEY] = updated_history
        session.modified = True
        return jsonify({'reply': reply})

    except ValueError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@coach_bp.route('/clear', methods=['POST'])
@login_required
def clear():
    """Clear the conversation history."""
    session.pop(HISTORY_SESSION_KEY, None)
    return jsonify({'status': 'cleared'})


@coach_bp.route('/generate-quest', methods=['POST'])
@login_required
def generate_quest():
    """Generate a personalised AI quest for the current user."""
    recent_foods = get_recent_foods(current_user.id)

    try:
        quest_data = generate_personalised_quest(current_user, recent_foods)
    except Exception:
        flash('Could not generate a quest right now. Please try again later.', 'warning')
        return redirect(url_for('quests.index'))

    # Check the user doesn't already have this exact quest title active
    existing = Quest.query.filter_by(
        title=quest_data['title'],
        ai_generated_for_user=current_user.id
    ).first()

    if existing:
        flash('You already have a similar AI quest active!', 'info')
        return redirect(url_for('quests.index'))

    # Save the new quest
    quest = Quest(
        title                = quest_data['title'],
        description          = quest_data['description'],
        icon                 = quest_data['icon'],
        difficulty           = quest_data['difficulty'],
        xp_reward            = quest_data['xp_reward'],
        criteria_type        = quest_data['criteria_type'],
        criteria_target      = quest_data['criteria_target'],
        quest_type           = 'ai_generated',
        is_active            = True,
        ai_generated_for_user = current_user.id,
    )
    db.session.add(quest)
    db.session.flush()  # get quest.id before committing

    # Assign it immediately to the user
    uq = UserQuest(user_id=current_user.id, quest_id=quest.id)
    db.session.add(uq)
    db.session.commit()

    # Small XP bonus for generating a quest
    award_xp(current_user, 5, reason='Generated AI quest')

    flash(f'{quest.icon} New personalised quest generated: {quest.title}!', 'success')
    return redirect(url_for('quests.index'))
