from app import app, db
from models import Player, Match, MatchPlayer

def init_db():
    with app.app_context():
        # Veritabanını oluştur
        db.create_all()
        print("Veritabanı tabloları başarıyla oluşturuldu!")

if __name__ == '__main__':
    init_db() 