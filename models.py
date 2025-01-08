from datetime import datetime, timezone
from pymongo import MongoClient
from bson import ObjectId
from config import Config

# MongoDB bağlantısı
client = MongoClient(Config.MONGO_URI)
db = client[Config.MONGO_DB]

# Koleksiyonlar
players = db.players
matches = db.matches
reactions = db.reactions

# Admin API key
API_KEY = "AE52YAPAR"

class Player:
    @staticmethod
    def get_by_id(id):
        player = players.find_one({"_id": str(id)})
        if player:
            # Stats değerlerini düzenle
            stats = player.get('stats', {})
            player['stats'] = {
                'pace': stats.get('pace', 70),
                'shooting': stats.get('shooting', 70),
                'passing': stats.get('passing', 70),
                'dribbling': stats.get('dribbling', 70),
                'defending': stats.get('defending', 70),
                'physical': stats.get('physical', 70)
            }
            
            # Overall değerini hesapla
            weights = {
                'Kaleci': {'pace': 0.1, 'shooting': 0, 'passing': 0.2, 'dribbling': 0.1, 'defending': 0.4, 'physical': 0.2},
                'Defans': {'pace': 0.2, 'shooting': 0.1, 'passing': 0.2, 'dribbling': 0.1, 'defending': 0.3, 'physical': 0.1},
                'Orta Saha': {'pace': 0.15, 'shooting': 0.2, 'passing': 0.25, 'dribbling': 0.2, 'defending': 0.1, 'physical': 0.1},
                'Forvet': {'pace': 0.2, 'shooting': 0.3, 'passing': 0.15, 'dribbling': 0.2, 'defending': 0.05, 'physical': 0.1}
            }
            
            w = weights.get(player.get('position', 'Orta Saha'))
            player['overall'] = int(
                player['stats']['pace'] * w['pace'] +
                player['stats']['shooting'] * w['shooting'] +
                player['stats']['passing'] * w['passing'] +
                player['stats']['dribbling'] * w['dribbling'] +
                player['stats']['defending'] * w['defending'] +
                player['stats']['physical'] * w['physical']
            )
        return player
    
    @staticmethod
    def get_all_active():
        return list(players.find({"is_active": True}))
    
    @staticmethod
    def get_stats(player_id):
        """Oyuncunun maç istatistiklerini hesaplar"""
        matches_played = []
        total_matches = 0
        wins = 0
        draws = 0
        
        # Oyuncunun katıldığı tüm maçları bul
        all_matches = list(matches.find())
        for match in all_matches:
            player_found = False
            for team in ['a', 'b']:
                for player in match['teams'][team]:
                    if player['player_id'] == str(player_id):
                        player_found = True
                        total_matches += 1
                        
                        # Galibiyet/beraberlik durumunu kontrol et
                        if match['score'].get('team_a') is not None and match['score'].get('team_b') is not None:
                            if match['score']['team_a'] == match['score']['team_b']:
                                draws += 1
                            elif (team == 'a' and match['score']['team_a'] > match['score']['team_b']) or \
                                 (team == 'b' and match['score']['team_b'] > match['score']['team_a']):
                                wins += 1
                                
                        # Maç detaylarını ekle
                        matches_played.append({
                            'date': match['date'],
                            'location': match['location'],
                            'score_team_a': match['score'].get('team_a'),
                            'score_team_b': match['score'].get('team_b'),
                            'is_winner': (team == 'a' and match['score'].get('team_a', 0) > match['score'].get('team_b', 0)) or \
                                       (team == 'b' and match['score'].get('team_b', 0) > match['score'].get('team_a', 0)),
                            'is_draw': match['score'].get('team_a') == match['score'].get('team_b'),
                            'has_paid': player.get('has_paid', False),
                            'payment_amount': player.get('payment_amount', 0)
                        })
                        break
                if player_found:
                    break
        
        return {
            'total_matches': total_matches,
            'wins': wins,
            'draws': draws,
            'losses': total_matches - wins - draws,
            'win_rate': (wins / total_matches * 100) if total_matches > 0 else 0,
            'match_history': sorted(matches_played, key=lambda x: x['date'], reverse=True)
        }

    @staticmethod
    def get_reactions(player_id):
        # Beğeni ve beğenmeme sayılarını getir
        reaction_stats = reactions.aggregate([
            {'$match': {'player_id': str(player_id)}},
            {'$group': {
                '_id': '$type',
                'count': {'$sum': 1}
            }}
        ])
        
        result = {'likes': 0, 'dislikes': 0}
        for stat in reaction_stats:
            if stat['_id'] == 'like':
                result['likes'] = stat['count']
            elif stat['_id'] == 'dislike':
                result['dislikes'] = stat['count']
        
        return result

    @staticmethod
    def get_comments(player_id):
        # Oyuncunun yorumlarını getir
        return list(reactions.find(
            {'player_id': str(player_id), 'comment': {'$exists': True}},
            {'comment': 1, 'created_at': 1, 'commenter_name': 1, 'is_admin': 1}
        ).sort('created_at', -1))

class Match:
    @staticmethod
    def get_by_id(id):
        try:
            print(f"Maç aranıyor. ID: {id}")  # Debug log
            # ID string olarak geldiğinden direkt olarak kullan
            match = matches.find_one({"_id": str(id)})
            
            if match:
                print(f"Maç bulundu: {match}")  # Debug log
                return match
                
            print(f"Maç bulunamadı. ID: {id}")  # Debug log
            return None
        except Exception as e:
            print(f"Maç getirme hatası: {str(e)}")  # Debug log
            return None
    
    @staticmethod
    def get_all():
        return list(matches.find().sort("date", -1))
    
    @staticmethod
    def create(match_data):
        try:
            # ObjectId oluştur
            match_id = ObjectId()
            match_data["_id"] = match_id
            match_data["created_at"] = datetime.now(timezone.utc)
            
            # MongoDB'ye kaydet
            matches.insert_one(match_data)
            
            # String olarak ID'yi döndür
            return str(match_id)
        except Exception as e:
            print(f"Maç oluşturma hatası: {str(e)}")
            return None

    @staticmethod
    def update(id, update_data):
        matches.update_one(
            {"_id": str(id)},
            {"$set": update_data}
        )

    @staticmethod
    def delete(id):
        matches.delete_one({"_id": str(id)})

    @staticmethod
    def toggle_payment(match_id, player_id):
        match = matches.find_one({"_id": str(match_id)})
        if not match:
            return False
        
        for team in ["a", "b"]:
            for player in match["teams"][team]:
                if player["player_id"] == str(player_id):
                    player["has_paid"] = not player["has_paid"]
                    matches.update_one(
                        {"_id": str(match_id)},
                        {"$set": {"teams": match["teams"]}}
                    )
                    return True
        return False 

    @staticmethod
    def get_player_stats(player_id):
        try:
            # Oyuncunun tüm maçlarını bul
            pipeline = [
                {
                    "$match": {
                        "$or": [
                            {"teams.a.player_id": str(player_id)},
                            {"teams.b.player_id": str(player_id)}
                        ]
                    }
                }
            ]
            player_matches = list(matches.aggregate(pipeline))
            print(f"Oyuncunun maçları: {player_matches}")  # Debug log
            
            total_matches = len(player_matches)
            wins = 0
            draws = 0
            match_history = []
            
            for match in player_matches:
                # Oyuncunun hangi takımda olduğunu bul
                team = 'a' if any(p['player_id'] == str(player_id) for p in match['teams']['a']) else 'b'
                
                is_winner = False
                is_draw = False
                
                if match['score'].get('team_a') is not None and match['score'].get('team_b') is not None:
                    if match['score']['team_a'] == match['score']['team_b']:
                        is_draw = True
                        draws += 1
                    else:
                        if team == 'a':
                            is_winner = match['score']['team_a'] > match['score']['team_b']
                        else:
                            is_winner = match['score']['team_b'] > match['score']['team_a']
                        
                        if is_winner:
                            wins += 1
                
                # Oyuncunun ödeme durumunu bul
                player_info = next(p for p in match['teams'][team] if p['player_id'] == str(player_id))
                
                # MongoDB ObjectId'yi string'e çevir
                match_id = str(match['_id'])
                
                match_history.append({
                    'match_id': match_id,
                    'date': match['date'],
                    'location': match['location'],
                    'score_team_a': match['score'].get('team_a'),
                    'score_team_b': match['score'].get('team_b'),
                    'is_winner': is_winner,
                    'is_draw': is_draw,
                    'has_paid': player_info['has_paid'],
                    'payment_amount': player_info['payment_amount']
                })
            
            # Ödeme istatistiklerini hesapla
            payment_stats = {
                'total_debt': "{:.2f}".format(sum(m['payment_amount'] for m in match_history)),
                'total_paid': "{:.2f}".format(sum(m['payment_amount'] for m in match_history if m['has_paid'])),
                'remaining': "{:.2f}".format(sum(m['payment_amount'] for m in match_history if not m['has_paid']))
            }
            
            return {
                'total_matches': total_matches,
                'wins': wins,
                'draws': draws,
                'losses': total_matches - wins - draws,
                'win_rate': (wins / total_matches * 100) if total_matches > 0 else 0,
                'match_history': match_history,
                'payment_stats': payment_stats
            }
        except Exception as e:
            print(f"Maç getirme hatası: {str(e)}")
            return None 