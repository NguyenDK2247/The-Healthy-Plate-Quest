from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.badge import UserBadge

profile_bp = Blueprint('profile', __name__)


@profile_bp.route('/')
@login_required
def index():
    all_user_badges = UserBadge.query.filter_by(
        user_id=current_user.id
    ).order_by(UserBadge.earned_at.desc()).all()
    featured = [ub for ub in all_user_badges if ub.is_featured]
    return render_template('profile/index.html',
                           all_user_badges=all_user_badges,
                           featured=featured)


@profile_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    if request.method == 'POST':
        errors = []

        # ── Username ──────────────────────────────────────────────────────
        new_username = request.form.get('username', '').strip()
        if not new_username or len(new_username) < 3:
            errors.append('Username must be at least 3 characters.')
        elif new_username != current_user.username:
            taken = User.query.filter_by(username=new_username).first()
            if taken:
                errors.append('That username is already taken.')

        # ── Password ──────────────────────────────────────────────────────
        current_pw  = request.form.get('current_password', '')
        new_pw      = request.form.get('new_password', '')
        confirm_pw  = request.form.get('confirm_password', '')

        changing_password = bool(current_pw or new_pw or confirm_pw)
        if changing_password:
            if not current_user.check_password(current_pw):
                errors.append('Current password is incorrect.')
            elif len(new_pw) < 6:
                errors.append('New password must be at least 6 characters.')
            elif new_pw != confirm_pw:
                errors.append('New passwords do not match.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('profile/edit.html')

        # ── Save all fields ───────────────────────────────────────────────
        current_user.username     = new_username
        current_user.display_name = request.form.get('display_name', '').strip() or new_username
        current_user.bio          = request.form.get('bio', '').strip()
        current_user.avatar_url   = request.form.get('avatar_url', current_user.avatar_url)
        current_user.nutrition_goal        = request.form.get('nutrition_goal', 'general')
        current_user.dietary_preference    = request.form.get('dietary_preference', 'omnivore')
        current_user.dietary_restrictions  = request.form.get('dietary_restrictions', '')
        current_user.favorite_ingredients  = request.form.get('favorite_ingredients', '')

        if changing_password:
            current_user.set_password(new_pw)
            flash('Password updated successfully.', 'success')

        db.session.commit()
        flash('Profile saved!', 'success')
        return redirect(url_for('profile.index'))

    return render_template('profile/edit.html')


@profile_bp.route('/feature-badge/<int:ub_id>', methods=['POST'])
@login_required
def feature_badge(ub_id):
    ub = UserBadge.query.filter_by(id=ub_id, user_id=current_user.id).first_or_404()
    featured_count = UserBadge.query.filter_by(
        user_id=current_user.id, is_featured=True
    ).count()
    if not ub.is_featured and featured_count >= 3:
        flash('You can only feature up to 3 badges.', 'warning')
    else:
        ub.is_featured = not ub.is_featured
        db.session.commit()
    return redirect(url_for('profile.index'))
