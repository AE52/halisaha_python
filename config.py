import os
from datetime import timedelta

class Config:
    # SQLite yerine PostgreSQL kullanabiliriz
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///halisaha.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    ADMIN_API_KEY = os.getenv('ADMIN_API_KEY', 'AE52YAPAR')
    JWT_EXPIRATION_DELTA = timedelta(hours=24) 