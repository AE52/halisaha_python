from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# User modelini kaldırıyoruz ve yerine basit bir API_KEY tanımlıyoruz
API_KEY = "AE52YAPAR"

class PlayerComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    commenter_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    likes = db.Column(db.Integer, default=0)
    is_admin_comment = db.Column(db.Boolean, default=False)

class PlayerLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    liker_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    is_like = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin_reaction = db.Column(db.Boolean, default=False)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    tc_no = db.Column(db.String(11), unique=True, nullable=True)
    position = db.Column(db.String(50))
    pace = db.Column(db.Integer, default=70)
    shooting = db.Column(db.Integer, default=70)
    passing = db.Column(db.Integer, default=70)
    dribbling = db.Column(db.Integer, default=70)
    defending = db.Column(db.Integer, default=70)
    physical = db.Column(db.Integer, default=70)
    is_active = db.Column(db.Boolean, default=True)
    
    # İlişkiler
    comments_received = db.relationship('PlayerComment',
                                      foreign_keys='PlayerComment.player_id',
                                      backref='player', lazy='dynamic')
    comments_made = db.relationship('PlayerComment',
                                  foreign_keys='PlayerComment.commenter_id',
                                  backref='commenter', lazy='dynamic')
    likes_received = db.relationship('PlayerLike',
                                   foreign_keys='PlayerLike.player_id',
                                   backref='player', lazy='dynamic')
    likes_given = db.relationship('PlayerLike',
                                foreign_keys='PlayerLike.liker_id',
                                backref='liker', lazy='dynamic')
    
    @property
    def overall(self):
        # Pozisyona göre farklı stat ağırlıkları
        weights = {
            'Kaleci': {'pace': 0.1, 'shooting': 0, 'passing': 0.2, 'dribbling': 0.1, 'defending': 0.4, 'physical': 0.2},
            'Defans': {'pace': 0.2, 'shooting': 0.1, 'passing': 0.2, 'dribbling': 0.1, 'defending': 0.3, 'physical': 0.1},
            'Orta Saha': {'pace': 0.15, 'shooting': 0.2, 'passing': 0.25, 'dribbling': 0.2, 'defending': 0.1, 'physical': 0.1},
            'Forvet': {'pace': 0.2, 'shooting': 0.3, 'passing': 0.15, 'dribbling': 0.2, 'defending': 0.05, 'physical': 0.1}
        }
        
        w = weights.get(self.position, weights['Orta Saha'])
        return int(
            self.pace * w['pace'] +
            self.shooting * w['shooting'] +
            self.passing * w['passing'] +
            self.dribbling * w['dribbling'] +
            self.defending * w['defending'] +
            self.physical * w['physical']
        )

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    total_cost = db.Column(db.Float, nullable=False)
    score_team_a = db.Column(db.Integer)
    score_team_b = db.Column(db.Integer)
    
    # İlişkileri düzelt
    match_players = db.relationship(
        'MatchPlayer',
        cascade='all, delete-orphan',
        lazy=True,
        backref=db.backref('match', lazy=True)
    )
    
    players = db.relationship(
        'Player',
        secondary='match_player',
        backref=db.backref('matches', lazy=True)
    )
    
    @property
    def is_upcoming(self):
        return self.date > datetime.now()
    
    @property
    def time_remaining(self):
        if not self.is_upcoming:
            return None
        delta = self.date - datetime.now()
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        return {'days': days, 'hours': hours, 'minutes': minutes}

class MatchPlayer(db.Model):
    __tablename__ = 'match_player'
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'))
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    team = db.Column(db.String(1))  # 'A' veya 'B'
    has_paid = db.Column(db.Boolean, default=False)
    payment_amount = db.Column(db.Float)
    
    # İlişkileri kaldır (artık backref kullanıyoruz)
    player = db.relationship('Player', backref=db.backref('match_players', lazy=True)) 