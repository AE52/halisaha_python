import os
from datetime import timedelta

class Config:
    # MongoDB bağlantı bilgileri
    MONGO_URI = "mongodb+srv://ae52:Erenemir1comehacker@cluster0.y5nv8.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    DB_NAME = "halisaha_db"
    
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    ADMIN_API_KEY = os.getenv('ADMIN_API_KEY', 'AE52YAPAR')
    JWT_EXPIRATION_DELTA = timedelta(hours=24) 