from app import create_app, db
from app.models import User, FoodLog, Quest, UserQuest, Badge, UserBadge, LeaderboardEntry
from app.models.badge import DEFAULT_BADGES

app = create_app('development')


@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'FoodLog': FoodLog,
        'Quest': Quest,
        'UserQuest': UserQuest,
        'Badge': Badge,
        'UserBadge': UserBadge,
        'LeaderboardEntry': LeaderboardEntry,
    }


@app.cli.command('init-db')
def init_db():
    """Initialize the database and seed default data."""
    db.create_all()
    print('✅ Database tables created.')

    # Seed default badges if not already present
    if Badge.query.count() == 0:
        for badge_data in DEFAULT_BADGES:
            badge = Badge(**badge_data)
            db.session.add(badge)
        db.session.commit()
        print(f'✅ Seeded {len(DEFAULT_BADGES)} default badges.')
    else:
        print('ℹ️  Badges already seeded.')

    # Seed a few starter quests
    if Quest.query.count() == 0:
        starter_quests = [
            Quest(title='Veggie Starter', description='Log 3 vegetable servings today.',
                  quest_type='daily', category='vegetables', difficulty='easy',
                  xp_reward=30, icon='🥦', criteria_type='log_vegetables', criteria_target=3),
            Quest(title='Rainbow Plate', description='Eat 5 different colored foods today.',
                  quest_type='daily', category='variety', difficulty='medium',
                  xp_reward=50, icon='🌈', criteria_type='color_variety', criteria_target=5),
            Quest(title='Protein Week', description='Log a protein source for 4 days this week.',
                  quest_type='weekly', category='protein', difficulty='medium',
                  xp_reward=100, icon='💪', criteria_type='log_protein_days', criteria_target=4),
            Quest(title='Fiber Hero', description='Log at least 25g of fiber in one day.',
                  quest_type='weekly', category='fiber', difficulty='hard',
                  xp_reward=80, icon='🌾', criteria_type='daily_fiber_goal', criteria_target=25),
            Quest(title='Breakfast Champion', description='Log breakfast 5 days in a row.',
                  quest_type='weekly', category='consistency', difficulty='medium',
                  xp_reward=75, icon='🌅', criteria_type='log_breakfast_streak', criteria_target=5),
        ]
        for q in starter_quests:
            db.session.add(q)
        db.session.commit()
        print(f'✅ Seeded {len(starter_quests)} starter quests.')
    else:
        print('ℹ️  Quests already seeded.')

    print('🎉 Database initialization complete!')


if __name__ == '__main__':
    app.run(debug=True)
