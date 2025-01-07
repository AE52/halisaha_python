from app import app, db
from models import Player
import random

def create_random_stats(position):
    base_stats = {
        'Kaleci': {
            'pace': (50, 70),
            'shooting': (30, 50),
            'passing': (50, 70),
            'dribbling': (30, 50),
            'defending': (70, 90),
            'physical': (60, 80)
        },
        'Defans': {
            'pace': (60, 80),
            'shooting': (40, 60),
            'passing': (60, 75),
            'dribbling': (50, 70),
            'defending': (70, 85),
            'physical': (70, 85)
        },
        'Orta Saha': {
            'pace': (65, 80),
            'shooting': (65, 80),
            'passing': (70, 85),
            'dribbling': (70, 85),
            'defending': (60, 75),
            'physical': (65, 80)
        },
        'Forvet': {
            'pace': (70, 85),
            'shooting': (75, 90),
            'passing': (60, 75),
            'dribbling': (70, 85),
            'defending': (30, 50),
            'physical': (65, 80)
        }
    }
    
    stats = base_stats[position]
    return {
        'pace': random.randint(*stats['pace']),
        'shooting': random.randint(*stats['shooting']),
        'passing': random.randint(*stats['passing']),
        'dribbling': random.randint(*stats['dribbling']),
        'defending': random.randint(*stats['defending']),
        'physical': random.randint(*stats['physical'])
    }

players_data = [
    {'name': 'Aykut', 'position': 'Orta Saha'},
    {'name': 'Muratcan', 'position': 'Forvet'},
    {'name': 'Bilal D.', 'position': 'Defans'},
    {'name': 'Musa', 'position': 'Orta Saha'},
    {'name': 'Alperen', 'position': 'Forvet'},
    {'name': 'Burak Reha', 'position': 'Defans'},
    {'name': 'Yusuf', 'position': 'Orta Saha'},
    {'name': 'Eren', 'position': 'Kaleci'},
    {'name': 'Mustafa', 'position': 'Defans'},
    {'name': 'Berat', 'position': 'Orta Saha'},
    {'name': 'Emin', 'position': 'Forvet'},
    {'name': 'Aras', 'position': 'Orta Saha'},
    {'name': 'Üzeyir', 'position': 'Defans'},
    {'name': 'Boran', 'position': 'Forvet'},
    {'name': 'Serhan', 'position': 'Orta Saha'},
    {'name': 'Bilal Aktaş', 'position': 'Defans'},
    {'name': 'Esad', 'position': 'Orta Saha'}
]

def init_db():
    with app.app_context():
        # Veritabanını temizle ve yeniden oluştur
        db.drop_all()
        db.create_all()
        
        # Oyuncuları ekle
        for player_data in players_data:
            stats = create_random_stats(player_data['position'])
            player = Player(
                name=player_data['name'],
                position=player_data['position'],
                pace=stats['pace'],
                shooting=stats['shooting'],
                passing=stats['passing'],
                dribbling=stats['dribbling'],
                defending=stats['defending'],
                physical=stats['physical']
            )
            db.session.add(player)
        
        db.session.commit()

if __name__ == '__main__':
    init_db() 