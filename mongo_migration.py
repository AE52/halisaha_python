from pymongo import MongoClient
import sqlite3
from datetime import datetime, timezone
from bson import ObjectId

# MongoDB bağlantı bilgileri
MONGO_URI = "mongodb+srv://ae52:Erenemir1comehacker@cluster0.y5nv8.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
DB_NAME = "halisaha_db"

def connect_mongo():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME]

def get_sqlite_connection():
    return sqlite3.connect('instance/halisaha.db')

def migrate_players(mongo_db, sqlite_cur):
    players_collection = mongo_db.players
    
    # Mevcut oyuncuları al
    sqlite_cur.execute("""
        SELECT id, name, tc_no, position, pace, shooting, passing, 
               dribbling, defending, physical, is_active 
        FROM player
    """)
    players = sqlite_cur.fetchall()
    
    # MongoDB'ye aktar
    for player in players:
        player_doc = {
            "_id": str(player[0]),
            "name": player[1],
            "tc_no": player[2],
            "position": player[3],
            "stats": {
                "pace": player[4],
                "shooting": player[5],
                "passing": player[6],
                "dribbling": player[7],
                "defending": player[8],
                "physical": player[9]
            },
            "is_active": bool(player[10]),
            "created_at": datetime.now(timezone.utc)
        }
        players_collection.insert_one(player_doc)

def migrate_matches(mongo_db, sqlite_cur):
    matches_collection = mongo_db.matches
    
    # Maçları al
    sqlite_cur.execute("""
        SELECT id, date, location, total_cost, score_team_a, score_team_b
        FROM match
    """)
    matches = sqlite_cur.fetchall()
    
    for match in matches:
        # Maça ait oyuncuları al
        sqlite_cur.execute("""
            SELECT player_id, team, has_paid, payment_amount
            FROM match_player
            WHERE match_id = ?
        """, (match[0],))
        match_players = sqlite_cur.fetchall()
        
        players_a = []
        players_b = []
        
        for mp in match_players:
            player_info = {
                "player_id": str(mp[0]),
                "has_paid": bool(mp[2]),
                "payment_amount": float(mp[3])
            }
            if mp[1] == 'A':
                players_a.append(player_info)
            else:
                players_b.append(player_info)

        # Tarih formatını düzelt
        try:
            match_date = datetime.strptime(match[1].split('.')[0], '%Y-%m-%d %H:%M:%S')
            match_date = match_date.replace(tzinfo=timezone.utc)
        except:
            match_date = datetime.now(timezone.utc)
        
        match_doc = {
            "_id": str(match[0]),
            "date": match_date,
            "location": match[2],
            "total_cost": float(match[3]),
            "score": {
                "team_a": match[4],
                "team_b": match[5]
            },
            "teams": {
                "a": players_a,
                "b": players_b
            },
            "created_at": datetime.now(timezone.utc)
        }
        matches_collection.insert_one(match_doc)

def migrate_likes_comments(mongo_db, sqlite_cur):
    reactions_collection = mongo_db.reactions
    
    # Beğenileri al
    sqlite_cur.execute("""
        SELECT id, player_id, liker_id, is_like, created_at, is_admin_reaction
        FROM player_like
    """)
    likes = sqlite_cur.fetchall()
    
    # Yorumları al
    sqlite_cur.execute("""
        SELECT id, player_id, commenter_id, comment, created_at, is_admin_comment
        FROM player_comment
    """)
    comments = sqlite_cur.fetchall()
    
    # Beğenileri aktar
    for like in likes:
        try:
            created_at = datetime.strptime(like[4].split('.')[0], '%Y-%m-%d %H:%M:%S')
            created_at = created_at.replace(tzinfo=timezone.utc)
        except:
            created_at = datetime.now(timezone.utc)

        like_doc = {
            "_id": f"like_{like[0]}",
            "type": "like",
            "player_id": str(like[1]),
            "liker_id": str(like[2]),
            "is_like": bool(like[3]),
            "created_at": created_at,
            "is_admin_reaction": bool(like[5])
        }
        reactions_collection.insert_one(like_doc)
    
    # Yorumları aktar
    for comment in comments:
        try:
            created_at = datetime.strptime(comment[4].split('.')[0], '%Y-%m-%d %H:%M:%S')
            created_at = created_at.replace(tzinfo=timezone.utc)
        except:
            created_at = datetime.now(timezone.utc)

        comment_doc = {
            "_id": f"comment_{comment[0]}",
            "type": "comment",
            "player_id": str(comment[1]),
            "commenter_id": str(comment[2]),
            "comment": comment[3],
            "created_at": created_at,
            "is_admin_comment": bool(comment[5])
        }
        reactions_collection.insert_one(comment_doc)

def main():
    try:
        # MongoDB'ye bağlan
        mongo_db = connect_mongo()
        
        # SQLite bağlantısı
        sqlite_conn = get_sqlite_connection()
        sqlite_cur = sqlite_conn.cursor()
        
        # Koleksiyonları temizle
        print("Koleksiyonlar temizleniyor...")
        mongo_db.players.delete_many({})
        mongo_db.matches.delete_many({})
        mongo_db.reactions.delete_many({})
        
        # Verileri aktar
        print("Oyuncular aktarılıyor...")
        migrate_players(mongo_db, sqlite_cur)
        
        print("Maçlar aktarılıyor...")
        migrate_matches(mongo_db, sqlite_cur)
        
        print("Beğeniler ve yorumlar aktarılıyor...")
        migrate_likes_comments(mongo_db, sqlite_cur)
        
        print("Migrasyon tamamlandı!")
        
    except Exception as e:
        print(f"Hata oluştu: {str(e)}")
        import traceback
        traceback.print_exc()  # Detaylı hata mesajı
    finally:
        sqlite_conn.close()

if __name__ == "__main__":
    main() 