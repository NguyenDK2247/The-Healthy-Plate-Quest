import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    class ProductionConfig(Config):
        SECRET_KEY = os.environ.get('SECRET_KEY')
        if not SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable must be set in production")
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///healthy_plate_quest.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
