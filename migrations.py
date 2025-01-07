from app import app, db
from models import Player, PlayerComment, PlayerLike
from sqlalchemy import text

def add_new_tables():
    with app.app_context():
        try:
            # PlayerComment tablosunu oluştur
            with db.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS player_comment (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        player_id INTEGER,
                        commenter_id INTEGER,
                        comment TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        likes INTEGER DEFAULT 0,
                        FOREIGN KEY (player_id) REFERENCES player (id),
                        FOREIGN KEY (commenter_id) REFERENCES player (id)
                    )
                """))
                
                # PlayerLike tablosunu oluştur
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS player_like (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        player_id INTEGER,
                        liker_id INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (player_id) REFERENCES player (id),
                        FOREIGN KEY (liker_id) REFERENCES player (id)
                    )
                """))
                
                conn.commit()
                print("Yeni tablolar başarıyla oluşturuldu")
                
        except Exception as e:
            print(f"Hata oluştu: {str(e)}")
            raise e

def update_likes_table():
    with app.app_context():
        try:
            # Önce mevcut verileri yedekle
            with db.engine.connect() as conn:
                # Eski tabloyu yedekle
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS player_like_backup (
                        id INTEGER PRIMARY KEY,
                        player_id INTEGER,
                        liker_id INTEGER,
                        created_at DATETIME,
                        FOREIGN KEY (player_id) REFERENCES player (id),
                        FOREIGN KEY (liker_id) REFERENCES player (id)
                    )
                """))
                
                # Mevcut verileri yedek tabloya kopyala
                conn.execute(text("""
                    INSERT INTO player_like_backup 
                    SELECT id, player_id, liker_id, created_at 
                    FROM player_like
                """))
                
                # Eski tabloyu sil
                conn.execute(text("DROP TABLE player_like"))
                
                # Yeni tabloyu oluştur
                conn.execute(text("""
                    CREATE TABLE player_like (
                        id INTEGER PRIMARY KEY,
                        player_id INTEGER,
                        liker_id INTEGER,
                        is_like BOOLEAN DEFAULT TRUE,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (player_id) REFERENCES player (id),
                        FOREIGN KEY (liker_id) REFERENCES player (id)
                    )
                """))
                
                # Eski verileri yeni tabloya aktar (varsayılan olarak tüm eski beğenileri like olarak işaretle)
                conn.execute(text("""
                    INSERT INTO player_like (id, player_id, liker_id, is_like, created_at)
                    SELECT id, player_id, liker_id, TRUE, created_at
                    FROM player_like_backup
                """))
                
                # Yedek tabloyu sil
                conn.execute(text("DROP TABLE player_like_backup"))
                
                conn.commit()
                print("Beğeni tablosu başarıyla güncellendi")
                
        except Exception as e:
            print(f"Hata oluştu: {str(e)}")
            # Hata durumunda yedek tabloyu temizle
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("DROP TABLE IF EXISTS player_like_backup"))
                    conn.commit()
            except:
                pass
            raise e

def add_admin_fields():
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                # PlayerComment tablosuna admin alanı ekle
                conn.execute(text("""
                    ALTER TABLE player_comment 
                    ADD COLUMN is_admin_comment BOOLEAN DEFAULT FALSE
                """))
                
                # PlayerLike tablosuna admin alanı ekle
                conn.execute(text("""
                    ALTER TABLE player_like 
                    ADD COLUMN is_admin_reaction BOOLEAN DEFAULT FALSE
                """))
                
                conn.commit()
                print("Admin alanları başarıyla eklendi")
                
        except Exception as e:
            print(f"Hata oluştu: {str(e)}")
            raise e

if __name__ == '__main__':
    add_new_tables()
    update_likes_table()
    add_admin_fields() 