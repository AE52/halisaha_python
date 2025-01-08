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
        try:
            # ID string olarak geliyor
            player = players.find_one({"_id": str(id)})
            if player:
                # Temel oyuncu bilgileri
                player_data = {
                    '_id': str(player['_id']),
                    'name': player.get('name', 'İsimsiz'),
                    'tc_no': player.get('tc_no', ''),
                    'position': player.get('position', 'Belirsiz'),
                    'stats': player.get('stats', {
                        'pace': 70,
                        'shooting': 70,
                        'passing': 70,
                        'dribbling': 70,
                        'defending': 70,
                        'physical': 70
                    }),
                    'is_active': player.get('is_active', True),
                    'created_at': player.get('created_at', datetime.now())
                }

                # Overall değerini hesapla
                weights = {
                    'Kaleci': {'pace': 0.1, 'shooting': 0, 'passing': 0.2, 'dribbling': 0.1, 'defending': 0.4, 'physical': 0.2},
                    'Defans': {'pace': 0.2, 'shooting': 0.1, 'passing': 0.2, 'dribbling': 0.1, 'defending': 0.3, 'physical': 0.1},
                    'Orta Saha': {'pace': 0.15, 'shooting': 0.2, 'passing': 0.25, 'dribbling': 0.2, 'defending': 0.1, 'physical': 0.1},
                    'Forvet': {'pace': 0.2, 'shooting': 0.3, 'passing': 0.15, 'dribbling': 0.2, 'defending': 0.05, 'physical': 0.1}
                }
                
                w = weights.get(player_data['position'], weights['Orta Saha'])
                player_data['overall'] = int(
                    player_data['stats']['pace'] * w['pace'] +
                    player_data['stats']['shooting'] * w['shooting'] +
                    player_data['stats']['passing'] * w['passing'] +
                    player_data['stats']['dribbling'] * w['dribbling'] +
                    player_data['stats']['defending'] * w['defending'] +
                    player_data['stats']['physical'] * w['physical']
                )

                # Maç istatistiklerini ekle
                match_stats = Player.get_player_stats(str(player['_id']))
                if match_stats:
                    player_data['match_stats'] = match_stats

                return player_data
            return None
        except Exception as e:
            print(f"ID ile oyuncu arama hatası: {str(e)}")
            return None

    @staticmethod
    def get_by_tc(tc_no):
        try:
            player = players.find_one({"tc_no": tc_no})
            if player:
                # Temel oyuncu bilgileri
                player_data = {
                    '_id': str(player['_id']),
                    'name': player.get('name', 'İsimsiz'),
                    'tc_no': player.get('tc_no', ''),
                    'position': player.get('position', 'Belirsiz'),
                    'stats': player.get('stats', {
                        'pace': 70,
                        'shooting': 70,
                        'passing': 70,
                        'dribbling': 70,
                        'defending': 70,
                        'physical': 70
                    }),
                    'is_active': player.get('is_active', True),
                    'created_at': player.get('created_at', datetime.now())
                }

                # Maç istatistiklerini ekle
                match_stats = Player.get_player_stats(str(player['_id']))
                if match_stats:
                    player_data['match_stats'] = match_stats

                return player_data
            return None
        except Exception as e:
            print(f"TC ile oyuncu arama hatası: {str(e)}")
            return None

    @staticmethod
    def get_all_active():
        try:
            # Aktif oyuncuları getir
            active_players = list(players.find({"is_active": True}))
            
            # Her oyuncu için bilgileri düzenle
            formatted_players = []
            for player in active_players:
                # Temel bilgiler
                player_data = {
                    '_id': str(player['_id']),
                    'name': player.get('name', 'İsimsiz'),
                    'position': player.get('position', 'Belirsiz'),
                    'stats': player.get('stats', {
                        'pace': 70,
                        'shooting': 70,
                        'passing': 70,
                        'dribbling': 70,
                        'defending': 70,
                        'physical': 70
                    })
                }

                # Overall değerini hesapla
                weights = {
                    'Kaleci': {'pace': 0.1, 'shooting': 0, 'passing': 0.2, 'dribbling': 0.1, 'defending': 0.4, 'physical': 0.2},
                    'Defans': {'pace': 0.2, 'shooting': 0.1, 'passing': 0.2, 'dribbling': 0.1, 'defending': 0.3, 'physical': 0.1},
                    'Orta Saha': {'pace': 0.15, 'shooting': 0.2, 'passing': 0.25, 'dribbling': 0.2, 'defending': 0.1, 'physical': 0.1},
                    'Forvet': {'pace': 0.2, 'shooting': 0.3, 'passing': 0.15, 'dribbling': 0.2, 'defending': 0.05, 'physical': 0.1}
                }
                
                w = weights.get(player_data['position'], weights['Orta Saha'])
                player_data['overall'] = int(
                    player_data['stats']['pace'] * w['pace'] +
                    player_data['stats']['shooting'] * w['shooting'] +
                    player_data['stats']['passing'] * w['passing'] +
                    player_data['stats']['dribbling'] * w['dribbling'] +
                    player_data['stats']['defending'] * w['defending'] +
                    player_data['stats']['physical'] * w['physical']
                )

                formatted_players.append(player_data)
            
            return formatted_players
        except Exception as e:
            print(f"Aktif oyuncuları getirme hatası: {str(e)}")
            return []

    @staticmethod
    def get_player_stats(player_id):
        try:
            # Oyuncunun tüm maçlarını bul
            player_matches = list(matches.find({
                "$or": [
                    {"teams.a.player_id": str(player_id)},
                    {"teams.b.player_id": str(player_id)}
                ]
            }).sort("date", -1))

            total_matches = len(player_matches)
            wins = 0
            draws = 0
            match_history = []
            total_debt = 0
            total_paid = 0

            for match in player_matches:
                # Oyuncunun hangi takımda olduğunu bul
                team = 'a' if any(p['player_id'] == str(player_id) for p in match['teams']['a']) else 'b'
                
                # Oyuncunun ödeme bilgilerini bul
                player_info = next(p for p in match['teams'][team] if p['player_id'] == str(player_id))
                
                # Skor ve kazanma durumunu kontrol et
                score_a = match['score'].get('team_a')
                score_b = match['score'].get('team_b')
                
                is_winner = False
                is_draw = False
                
                if score_a is not None and score_b is not None:
                    if score_a == score_b:
                        is_draw = True
                        draws += 1
                    else:
                        is_winner = (team == 'a' and score_a > score_b) or (team == 'b' and score_b > score_a)
                        if is_winner:
                            wins += 1

                # Ödeme durumunu kontrol et
                payment_amount = player_info.get('payment_amount', 0)
                has_paid = player_info.get('has_paid', False)
                
                if has_paid:
                    total_paid += payment_amount
                total_debt += payment_amount

                match_history.append({
                    'match_id': str(match['_id']),
                    'date': match['date'],
                    'location': match['location'],
                    'score_team_a': score_a,
                    'score_team_b': score_b,
                    'is_winner': is_winner,
                    'is_draw': is_draw,
                    'has_paid': has_paid,
                    'payment_amount': payment_amount
                })

            return {
                'total_matches': total_matches,
                'wins': wins,
                'draws': draws,
                'losses': total_matches - wins - draws,
                'win_rate': (wins / total_matches * 100) if total_matches > 0 else 0,
                'match_history': match_history,
                'payment_stats': {
                    'total_debt': "{:.2f}".format(total_debt),
                    'total_paid': "{:.2f}".format(total_paid),
                    'remaining': "{:.2f}".format(total_debt - total_paid)
                }
            }
        except Exception as e:
            print(f"Oyuncu istatistikleri getirme hatası: {str(e)}")
            return None 

    @staticmethod
    def get_reactions(player_id):
        try:
            # Beğeni ve beğenmeme sayılarını al
            likes = reactions.count_documents({
                "player_id": str(player_id),
                "type": "like",
                "is_like": True
            })
            
            dislikes = reactions.count_documents({
                "player_id": str(player_id),
                "type": "like",
                "is_like": False
            })
            
            return {
                'likes': likes,
                'dislikes': dislikes
            }
        except Exception as e:
            print(f"Beğeni sayılarını getirme hatası: {str(e)}")
            return {
                'likes': 0,
                'dislikes': 0
            }

    @staticmethod
    def get_user_reaction(player_id, user_id):
        try:
            reaction = reactions.find_one({
                "player_id": str(player_id),
                "liker_id": str(user_id),
                "type": "like"
            })
            
            if reaction:
                return "like" if reaction.get('is_like', False) else "dislike"
            return None
        except Exception as e:
            print(f"Kullanıcı beğenisini getirme hatası: {str(e)}")
            return None

    @staticmethod
    def add_or_update_reaction(player_id, user_id, is_like, is_admin=False):
        try:
            # Önceki reaksiyonu kontrol et
            existing = reactions.find_one({
                "player_id": str(player_id),
                "liker_id": str(user_id),
                "type": "like"
            })
            
            if existing:
                # Reaksiyonu güncelle
                reactions.update_one(
                    {"_id": existing['_id']},
                    {
                        "$set": {
                            "is_like": is_like,
                            "is_admin_reaction": is_admin
                        }
                    }
                )
            else:
                # Yeni reaksiyon ekle
                reactions.insert_one({
                    "type": "like",
                    "player_id": str(player_id),
                    "liker_id": str(user_id),
                    "is_like": is_like,
                    "is_admin_reaction": is_admin,
                    "created_at": datetime.now(timezone.utc)
                })
            
            return True
        except Exception as e:
            print(f"Beğeni ekleme/güncelleme hatası: {str(e)}")
            return False

class Match:
    @staticmethod
    def get_all():
        try:
            # Tüm maçları tarihe göre sırala (en yeni en üstte)
            all_matches = list(matches.find().sort("date", -1))
            
            # Her maç için oyuncu bilgilerini ekle
            for match in all_matches:
                match['_id'] = str(match['_id'])  # ObjectId'yi string'e çevir
                
                # Her takımdaki oyuncular için bilgileri al
                for team in ['a', 'b']:
                    for player in match['teams'][team]:
                        player_info = Player.get_by_id(player['player_id'])
                        if player_info:
                            player.update({
                                'name': player_info.get('name', 'İsimsiz'),
                                'position': player_info.get('position', 'Belirsiz'),
                                'stats': player_info.get('stats', {
                                    'pace': 70,
                                    'shooting': 70,
                                    'passing': 70,
                                    'dribbling': 70,
                                    'defending': 70,
                                    'physical': 70
                                })
                            })
            return all_matches
        except Exception as e:
            print(f"Maçları getirme hatası: {str(e)}")
            return []

    @staticmethod
    def get_by_id(id):
        try:
            # ID string olarak geliyor
            match = matches.find_one({"_id": str(id)})
            if match:
                match['_id'] = str(match['_id'])
                # Her oyuncu için bilgileri al
                for team in ['a', 'b']:
                    for player in match['teams'][team]:
                        player_info = Player.get_by_id(player['player_id'])
                        if player_info:
                            player.update({
                                'name': player_info.get('name', 'İsimsiz'),
                                'position': player_info.get('position', 'Belirsiz'),
                                'stats': player_info.get('stats', {
                                    'pace': 70,
                                    'shooting': 70,
                                    'passing': 70,
                                    'dribbling': 70,
                                    'defending': 70,
                                    'physical': 70
                                })
                            })
                return match
            return None
        except Exception as e:
            print(f"Maç getirme hatası: {str(e)}")
            return None

    @staticmethod
    def update(id, update_data):
        try:
            result = matches.update_one(
                {"_id": str(id)},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Maç güncelleme hatası: {str(e)}")
            return False

    @staticmethod
    def get_player_stats(player_id):
        try:
            # Oyuncunun tüm maçlarını bul
            player_matches = list(matches.find({
                "$or": [
                    {"teams.a.player_id": str(player_id)},
                    {"teams.b.player_id": str(player_id)}
                ]
            }).sort("date", -1))

            total_matches = len(player_matches)
            wins = 0
            draws = 0
            match_history = []
            total_debt = 0
            total_paid = 0

            for match in player_matches:
                # Oyuncunun hangi takımda olduğunu bul
                team = 'a' if any(p['player_id'] == str(player_id) for p in match['teams']['a']) else 'b'
                
                # Oyuncunun ödeme bilgilerini bul
                player_info = next(p for p in match['teams'][team] if p['player_id'] == str(player_id))
                
                # Skor ve kazanma durumunu kontrol et
                score_a = match['score'].get('team_a')
                score_b = match['score'].get('team_b')
                
                is_winner = False
                is_draw = False
                
                if score_a is not None and score_b is not None:
                    if score_a == score_b:
                        is_draw = True
                        draws += 1
                    else:
                        is_winner = (team == 'a' and score_a > score_b) or (team == 'b' and score_b > score_a)
                        if is_winner:
                            wins += 1

                # Ödeme durumunu kontrol et
                payment_amount = player_info.get('payment_amount', 0)
                has_paid = player_info.get('has_paid', False)
                
                if has_paid:
                    total_paid += payment_amount
                total_debt += payment_amount

                match_history.append({
                    'match_id': str(match['_id']),
                    'date': match['date'],
                    'location': match['location'],
                    'score_team_a': score_a,
                    'score_team_b': score_b,
                    'is_winner': is_winner,
                    'is_draw': is_draw,
                    'has_paid': has_paid,
                    'payment_amount': payment_amount
                })

            return {
                'total_matches': total_matches,
                'wins': wins,
                'draws': draws,
                'losses': total_matches - wins - draws,
                'win_rate': (wins / total_matches * 100) if total_matches > 0 else 0,
                'match_history': match_history,
                'payment_stats': {
                    'total_debt': "{:.2f}".format(total_debt),
                    'total_paid': "{:.2f}".format(total_paid),
                    'remaining': "{:.2f}".format(total_debt - total_paid)
                }
            }
        except Exception as e:
            print(f"Oyuncu istatistikleri getirme hatası: {str(e)}")
            return None 