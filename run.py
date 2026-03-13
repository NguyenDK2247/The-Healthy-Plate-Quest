from app import create_app, db
from app.models import User, FoodLog, Quest, UserQuest, Badge, UserBadge, LeaderboardEntry
from app.models.badge import DEFAULT_BADGES

app = create_app('development')


@app.shell_context_processor
def make_shell_context():
    return {
        'db': db, 'User': User, 'FoodLog': FoodLog, 'Quest': Quest,
        'UserQuest': UserQuest, 'Badge': Badge, 'UserBadge': UserBadge,
        'LeaderboardEntry': LeaderboardEntry,
    }


@app.cli.command('init-db')
def init_db():
    """Initialize the database and seed default data."""
    db.create_all()
    print('✅ Database tables created.')

    # Seed badges
    if Badge.query.count() == 0:
        for badge_data in DEFAULT_BADGES:
            db.session.add(Badge(**badge_data))
        db.session.commit()
        print(f'✅ Seeded {len(DEFAULT_BADGES)} badges.')
    else:
        print('ℹ️  Badges already seeded.')

    # Seed quests
    if Quest.query.count() == 0:
        starter_quests = [
            # Daily
            Quest(title='Veggie Starter', icon='🥦', quest_type='daily', category='vegetables',
                  difficulty='easy', xp_reward=30, criteria_type='log_vegetables', criteria_target=3,
                  description='Log 3 vegetable servings today.'),
            Quest(title='Rainbow Plate', icon='🌈', quest_type='daily', category='variety',
                  difficulty='medium', xp_reward=50, criteria_type='color_variety', criteria_target=5,
                  description='Eat 5 different colored foods today.'),
            Quest(title='Breakfast Champion', icon='🌅', quest_type='daily', category='consistency',
                  difficulty='easy', xp_reward=25, criteria_type='log_breakfast', criteria_target=1,
                  description='Log your breakfast today.'),
            Quest(title='Fruit Power', icon='🍓', quest_type='daily', category='fruit',
                  difficulty='easy', xp_reward=25, criteria_type='log_fruit', criteria_target=2,
                  description='Log 2 fruit servings today.'),
            Quest(title='Protein Pack', icon='🥩', quest_type='daily', category='protein',
                  difficulty='medium', xp_reward=40, criteria_type='log_protein', criteria_target=3,
                  description='Log 3 protein-rich foods today.'),
            # Weekly
            Quest(title='Protein Week', icon='💪', quest_type='weekly', category='protein',
                  difficulty='medium', xp_reward=100, criteria_type='log_protein_days', criteria_target=4,
                  description='Log a protein source for 4 days this week.'),
            Quest(title='Fiber Hero', icon='🌾', quest_type='weekly', category='fiber',
                  difficulty='hard', xp_reward=80, criteria_type='daily_fiber_goal', criteria_target=25,
                  description='Log at least 25g of fiber in one day this week.'),
            Quest(title='Veggie Week', icon='🥗', quest_type='weekly', category='vegetables',
                  difficulty='medium', xp_reward=90, criteria_type='log_vegetables_week', criteria_target=15,
                  description='Log 15 vegetable servings over the week.'),
            Quest(title='Meal Logger', icon='📋', quest_type='weekly', category='consistency',
                  difficulty='easy', xp_reward=60, criteria_type='log_meals_week', criteria_target=14,
                  description='Log at least 14 meals this week (2 per day).'),
        ]
        for q in starter_quests:
            db.session.add(q)
        db.session.commit()
        print(f'✅ Seeded {len(starter_quests)} quests.')
    else:
        print('ℹ️  Quests already seeded.')

    print('🎉 Database ready!')


if __name__ == '__main__':
    app.run(debug=True)
    