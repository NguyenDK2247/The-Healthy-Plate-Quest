from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access The Healthy Plate Quest!'
login_manager.login_message_category = 'info'


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.food_log import food_log_bp
    from app.routes.quests import quests_bp
    from app.routes.coach import coach_bp
    from app.routes.leaderboard import leaderboard_bp
    from app.routes.profile import profile_bp
    from app.routes.evaluation import evaluation_bp # type: ignore

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(food_log_bp, url_prefix='/log')
    app.register_blueprint(quests_bp, url_prefix='/quests')
    app.register_blueprint(coach_bp, url_prefix='/coach')
    app.register_blueprint(leaderboard_bp, url_prefix='/leaderboard')
    app.register_blueprint(profile_bp, url_prefix='/profile')
    app.register_blueprint(evaluation_bp, url_prefix='/eval')

    # User loader for Flask-Login
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    return app
