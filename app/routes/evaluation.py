"""
evaluation.py — Routes for user evaluation, feedback, and analytics export.

Routes:
  GET  /eval/survey          — SUS + AI coach questionnaire
  POST /eval/survey          — Submit survey responses
  GET  /eval/feedback        — Open-ended qualitative feedback form
  POST /eval/feedback        — Submit qualitative feedback
  GET  /eval/thankyou        — Post-submission thank you page
  GET  /eval/results         — Researcher dashboard (analytics summary)
  GET  /eval/export.csv      — Download CSV of all participant data
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, \
    Response, current_app
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.evaluation import UsabilityResponse, FeedbackResponse
from app.services.analytics import (
    log_event, get_user_stats, get_sus_summary, generate_csv_export
)
from app.models.user import User

evaluation_bp = Blueprint('evaluation', __name__)


@evaluation_bp.route('/survey', methods=['GET', 'POST'])
@login_required
def survey():
    # Check if already submitted
    existing = UsabilityResponse.query.filter_by(user_id=current_user.id).first()

    if request.method == 'POST':
        def gi(name):
            try:
                return int(request.form.get(name, 0))
            except (ValueError, TypeError):
                return None

        resp = UsabilityResponse(
            user_id            = current_user.id,
            q1  = gi('q1'),  q2  = gi('q2'),  q3  = gi('q3'),
            q4  = gi('q4'),  q5  = gi('q5'),  q6  = gi('q6'),
            q7  = gi('q7'),  q8  = gi('q8'),  q9  = gi('q9'),
            q10 = gi('q10'),
            ai_coach_motivated   = gi('ai_coach_motivated'),
            ai_coach_useful      = gi('ai_coach_useful'),
            ai_coach_personal    = gi('ai_coach_personal'),
            ai_coach_trustworthy = gi('ai_coach_trustworthy'),
        )

        # If already submitted, update instead
        if existing:
            db.session.delete(existing)

        db.session.add(resp)
        db.session.commit()

        log_event(current_user.id, 'survey_submitted',
                  {'sus_score': resp.sus_score})

        flash('Thank you for completing the usability survey! 🎉', 'success')
        return redirect(url_for('evaluation.feedback'))

    return render_template('evaluation/survey.html', existing=existing)


@evaluation_bp.route('/feedback', methods=['GET', 'POST'])
@login_required
def feedback():
    existing = FeedbackResponse.query.filter_by(user_id=current_user.id).first()

    if request.method == 'POST':
        resp = FeedbackResponse(
            user_id          = current_user.id,
            what_worked      = request.form.get('what_worked', '').strip(),
            what_didnt       = request.form.get('what_didnt', '').strip(),
            ai_coach_comment = request.form.get('ai_coach_comment', '').strip(),
            suggestion       = request.form.get('suggestion', '').strip(),
            would_recommend  = request.form.get('would_recommend') == 'yes',
            overall_rating   = int(request.form.get('overall_rating', 3)),
        )

        if existing:
            db.session.delete(existing)

        db.session.add(resp)
        db.session.commit()
        log_event(current_user.id, 'feedback_submitted')

        return redirect(url_for('evaluation.thankyou'))

    return render_template('evaluation/feedback.html', existing=existing)


@evaluation_bp.route('/thankyou')
@login_required
def thankyou():
    return render_template('evaluation/thankyou.html')


@evaluation_bp.route('/results')
@login_required
def results():
    """Researcher-facing analytics dashboard."""
    all_users  = User.query.all()
    user_stats = [get_user_stats(u) for u in all_users]
    sus_summary = get_sus_summary()

    # Engagement summary
    total_meals   = sum(s['total_meals'] for s in user_stats)
    total_quests  = sum(s['quests_completed'] for s in user_stats)
    total_coach   = sum(s['coach_messages'] for s in user_stats)
    avg_engage    = round(
        sum(s['engagement_rate'] for s in user_stats) / len(user_stats), 1
    ) if user_stats else 0

    return render_template('evaluation/results.html',
                           user_stats=user_stats,
                           sus_summary=sus_summary,
                           total_meals=total_meals,
                           total_quests=total_quests,
                           total_coach=total_coach,
                           avg_engage=avg_engage)


@evaluation_bp.route('/export.csv')
@login_required
def export_csv():
    """Download all participant data as a CSV file."""
    csv_data = generate_csv_export()
    filename = f'hpq_study_export_{datetime.utcnow().strftime("%Y%m%d_%H%M")}.csv'
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )
