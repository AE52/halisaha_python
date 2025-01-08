import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'gizli-anahtar-123'
    MONGO_URI = os.environ.get('MONGO_URI') or "mongodb+srv://ae52:Erenemir1comehacker@cluster0.y5nv8.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    MONGO_DB = os.environ.get('MONGO_DB') or 'halisaha_db'  # Veritabanı adını güncelledik
    JWT_EXPIRATION = timedelta(days=7) 
    CLOUDINARY_CLOUD_NAME = 'dqhheif0c'
    CLOUDINARY_API_KEY = '164851497378274'
    CLOUDINARY_API_SECRET = 'rKOL5XbXhqbheFG-xahvLsSthh4' 