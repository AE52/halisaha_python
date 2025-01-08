from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory, make_response
from models import Player, Match, API_KEY  # MatchPlayer ve diğer modelleri kaldır
from config import Config
from functools import wraps
from translations import translations
import jwt
from pymongo import MongoClient
import os
from bson import ObjectId
import pytz  # Ekleyin
from werkzeug.utils import secure_filename
import time
import cloudinary
import cloudinary.uploader
import shutil
import requests

app = Flask(__name__)
app.config.from_object(Config)

# MongoDB bağlantısı
client = MongoClient(
    Config.MONGO_URI,
    serverSelectionTimeoutMS=5000,
    retryWrites=True,
    retryReads=True,
    connectTimeoutMS=30000,
    socketTimeoutMS=None,
    connect=False
)

# Veritabanı ve koleksiyonları tanımla
db = client[Config.MONGO_DB]
players_collection = db.players  # players yerine players_collection kullan
reactions = db.reactions  # Reaksiyonlar için koleksiyon
comments = db.comments  # Yorum koleksiyonunu ekle

# Bağlantıyı test et
try:
    client.admin.command('ping')
    print("MongoDB bağlantısı başarılı!")
except Exception as e:
    print(f"MongoDB bağlantı hatası: {str(e)}")

# Decorator'ları en üste taşıyalım
def admin_api_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            return jsonify({
                "error": "Bu işlem için admin yetkisi gereklidir",
                "redirect_url": url_for('admin_login')
            }), 403
        return f(*args, **kwargs)
    return decorated_function

def admin_page_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            flash('Bu sayfaya erişim için admin yetkisi gereklidir!', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Yetkilendirme yardımcı fonksiyonları
def get_user_type():
    """Kullanıcı tipini ve ID'sini döndür (admin, player veya None)"""
    try:
        # Admin kontrolü
        admin_token = request.cookies.get('jwt_token')
        if admin_token:
            try:
                jwt.decode(admin_token, app.config['SECRET_KEY'], algorithms=["HS256"])
                return 'admin', None
            except:
                pass

        # Oyuncu kontrolü
        player_token = request.cookies.get('player_token')
        if player_token and 'player_id' in session:
            try:
                data = jwt.decode(player_token, app.config['SECRET_KEY'], algorithms=["HS256"])
                player_id = data.get('player_id')
                if player_id and player_id == session['player_id']:
                    return 'player', player_id
            except:
                pass

    except Exception as e:
        print(f"Yetkilendirme hatası: {str(e)}")
    
    return None, None

def is_admin():
    """Admin yetkisi kontrolü"""
    try:
        token = request.cookies.get('jwt_token')
        if token:
            decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            return decoded.get('admin', False)
    except Exception as e:
        print(f"Admin kontrol hatası: {str(e)}")
    return False

def is_player():
    """Oyuncu girişi kontrolü"""
    user_type, _ = get_user_type()
    return user_type == 'player'

def get_current_user():
    """Mevcut kullanıcı bilgilerini döndür"""
    user_type, user_id = get_user_type()
    if user_type == 'admin':
        return {'is_admin': True, 'is_logged_in': False, 'current_user': None}
    elif user_type == 'player' and user_id:
        player = Player.get_by_id(user_id)
        if player:
            return {'is_admin': False, 'is_logged_in': True, 'current_user': player}
    return {'is_admin': False, 'is_logged_in': False, 'current_user': None}

# Admin decorator'ı güncellendi
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "Bu işlem için admin yetkisi gereklidir"}), 403
            flash('Bu sayfaya erişim için admin yetkisi gereklidir!', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Oyuncu decorator'ı güncellendi
def player_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_player():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "Bu işlem için oyuncu girişi gereklidir"}), 403
            flash('Bu işlem için giriş yapmalısınız!', 'error')
            return redirect(url_for('player_login'))
        return f(*args, **kwargs)
    return decorated_function

# Context processor güncellendi
@app.context_processor
def inject_user():
    return get_current_user()

# Giriş route'ları güncellendi
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    # Zaten giriş yapılmışsa yönlendir
    user_type, _ = get_user_type()
    if user_type:
        if user_type == 'admin':
            return redirect(url_for('index'))
        flash('Önce mevcut hesaptan çıkış yapmalısınız.', 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        api_key = request.form.get('api_key')
        if api_key == API_KEY:
            # JWT token oluştur - admin: True ekle
            token = jwt.encode({
                'admin': True,  # Bu önemli!
                'exp': datetime.utcnow() + timedelta(days=7)
            }, app.config['SECRET_KEY'])
            
            response = make_response(redirect(url_for('index')))
            response.set_cookie('jwt_token', token, httponly=True, secure=True, samesite='Lax')
            flash('Admin olarak giriş yapıldı', 'success')
            return response
        else:
            flash('Geçersiz API key!', 'error')
    return render_template('admin_login.html')

@app.route('/player-login', methods=['GET', 'POST'])
def player_login():
    # Zaten giriş yapılmışsa yönlendir
    user_type, _ = get_user_type()
    if user_type:
        if user_type == 'player':
            return redirect(url_for('index'))
        flash('Önce mevcut hesaptan çıkış yapmalısınız.', 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        tc_no = request.form.get('tc_no')
        player = Player.get_by_tc(tc_no)
        
        if player:
            token = jwt.encode({
                'player_id': str(player['_id']),
                'exp': datetime.utcnow() + timedelta(days=7)
            }, app.config['SECRET_KEY'])
            
            response = make_response(redirect(url_for('index')))
            response.set_cookie('player_token', token, httponly=True, secure=True, samesite='Lax')
            session['player_id'] = str(player['_id'])
            flash('Başarıyla giriş yapıldı', 'success')
            return response
        else:
            flash('TC kimlik numarası bulunamadı!', 'error')
    return render_template('player_login.html')

@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('index')))
    response.delete_cookie('jwt_token')
    response.delete_cookie('player_token')
    session.clear()
    flash('Başarıyla çıkış yapıldı', 'success')
    return response

@app.route('/')
def index():
    # Admin kontrolü
    is_admin = bool(request.cookies.get('jwt_token'))
    
    # Oyuncu kontrolü
    player_token = request.cookies.get('player_token')
    is_logged_in = False
    current_user = None
    
    if player_token:
        try:
            data = jwt.decode(player_token, app.config['SECRET_KEY'], algorithms=["HS256"])
            player_id = data.get('player_id')
            if player_id:
                current_user = Player.get_by_id(player_id)
                is_logged_in = True
        except:
            pass
    
    return render_template('index.html', 
                         is_admin=is_admin,
                         is_logged_in=is_logged_in,
                         current_user=current_user)

# Yardımcı fonksiyonlar
def get_translation(key, **kwargs):
    text = translations['tr'].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text

def get_player_card_class(overall):
    try:
        overall = int(overall)
        if overall >= 88:
            return 'elite'      # Mor (En üst seviye)
        elif overall >= 82:
            return 'gold'       # Altın (Yüksek seviye)
        elif overall >= 75:
            return 'silver'     # Gümüş (Orta seviye)
        else:
            return 'bronze'     # Bronz (Başlangıç seviye)
    except (TypeError, ValueError):
        return 'bronze'

# Türkiye saat dilimi için yardımcı fonksiyon
def get_turkey_time(utc_time=None):
    turkey_tz = pytz.timezone('Europe/Istanbul')
    if utc_time is None:
        utc_time = datetime.now(timezone.utc)
    elif not utc_time.tzinfo:
        utc_time = pytz.utc.localize(utc_time)
    return utc_time.astimezone(turkey_tz)

def country_to_flag_emoji(country_code):
    """Ülke kodunu bayrak emojisine çevirir"""
    if not country_code:
        return "🏳️"
        
    # Ülke kodunu büyük harfe çevir
    country_code = country_code.upper()
    
    # Regional Indicator Symbols'a çevir
    return "".join([chr(ord(c) + 127397) for c in country_code])

@app.context_processor
def utility_processor():
    def get_player_info(player_id):
        player = Player.get_by_id(player_id)
        if player:
            # Overall değerini hesapla
            stats = player.get('stats', {})
            weights = {
                'Kaleci': {'pace': 0.1, 'shooting': 0, 'passing': 0.2, 'dribbling': 0.1, 'defending': 0.4, 'physical': 0.2},
                'Defans': {'pace': 0.2, 'shooting': 0.1, 'passing': 0.2, 'dribbling': 0.1, 'defending': 0.3, 'physical': 0.1},
                'Orta Saha': {'pace': 0.15, 'shooting': 0.2, 'passing': 0.25, 'dribbling': 0.2, 'defending': 0.1, 'physical': 0.1},
                'Forvet': {'pace': 0.2, 'shooting': 0.3, 'passing': 0.15, 'dribbling': 0.2, 'defending': 0.05, 'physical': 0.1}
            }
            
            w = weights.get(player.get('position', 'Orta Saha'))
            player['overall'] = int(
                stats.get('pace', 70) * w['pace'] +
                stats.get('shooting', 70) * w['shooting'] +
                stats.get('passing', 70) * w['passing'] +
                stats.get('dribbling', 70) * w['dribbling'] +
                stats.get('defending', 70) * w['defending'] +
                stats.get('physical', 70) * w['physical']
            )
        return player

    return dict(
        translate=get_translation,
        get_player_card_class=get_player_card_class,
        get_stat_class=get_stat_class,
        get_player_info=get_player_info,
        get_turkey_time=get_turkey_time,
        country_to_flag_emoji=country_to_flag_emoji
    )

def get_stat_class(value):
    try:
        value = int(value)
        if value >= 85:
            return 'high'       # Yeşil (Çok iyi)
        elif value >= 75:
            return 'medium'     # Sarı (İyi)
        else:
            return 'low'        # Kırmızı (Geliştirilmeli)
    except (TypeError, ValueError):
        return 'low'

@app.route('/api/players', methods=['POST'])
@admin_required
def add_player_api():
    data = request.json
    try:
        # TC No kontrolü
        if 'tc_no' in data:
            existing_player = Player.get_by_tc(data['tc_no'])
            if existing_player:
                return jsonify({
                    "success": False,
                    "message": get_translation('tc_exists')
                }), 400

        # MongoDB'ye uygun formatta oyuncu verisi oluştur
        player_data = {
            "name": data['name'],
            "tc_no": data.get('tc_no'),
            "position": data['position'],
            "stats": {
                "pace": data['pace'],
                "shooting": data['shooting'],
                "passing": data['passing'],
                "dribbling": data['dribbling'],
                "defending": data['defending'],
                "physical": data['physical']
            },
            "is_active": True,
            "created_at": datetime.utcnow()
        }
        
        # Oyuncuyu ekle
        players_collection.insert_one(player_data)
        return jsonify({"success": True, "message": get_translation('player_added')})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@app.route('/api/players/<int:id>', methods=['PUT'])
@admin_required
def update_player_api(id):
    try:
        player = Player.query.get_or_404(id)
        data = request.json

        if 'tc_no' in data:
            # TC No kontrolü
            if data['tc_no'] != player.tc_no:
                existing = Player.query.filter_by(tc_no=data['tc_no']).first()
                if existing:
                    return jsonify({
                        'success': False,
                        'message': get_translation('tc_exists')
                    }), 400

            player.tc_no = data['tc_no']
            db.session.commit()

        return jsonify({
            'success': True,
            'message': get_translation('tc_updated')
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400

@app.route('/api/players/<int:id>', methods=['DELETE'])
@admin_required
def delete_player_api(id):
    player = Player.query.get_or_404(id)
    player.is_active = False
    db.session.commit()
    return jsonify({"msg": "Oyuncu başarıyla silindi"})

@app.route('/players')
def players():
    try:
        is_admin = bool(request.cookies.get('jwt_token'))
        players_list = Player.get_all_active()
        
        return render_template('players.html', 
                             players=players_list,
                             is_admin=is_admin)
    except Exception as e:
        flash(str(e), 'error')
        return redirect(url_for('index'))

@app.route('/matches')
def matches():
    try:
        is_admin = bool(request.cookies.get('jwt_token'))
        is_logged_in = bool(request.cookies.get('player_token'))
        matches_list = Match.get_all()
        
        # Şu anki zamanı ekle
        now = datetime.now()
        
        return render_template('matches.html', 
                             matches=matches_list,
                             is_admin=is_admin,
                             is_logged_in=is_logged_in,
                             now=now)
    except Exception as e:
        flash(str(e), 'error')
        return redirect(url_for('index'))

# Maç API endpoint'leri
@app.route('/api/matches', methods=['POST'])
@admin_required
def add_match_api():
    data = request.json
    try:
        # Tarihi parse et
        date_str = data['date']
        match_date = datetime.strptime(date_str, '%d/%m/%Y %H:%M')
        
        match = Match(
            date=match_date,
            location=data['location'],
            total_cost=float(data['total_cost'])
        )
        db.session.add(match)
        db.session.flush()
        
        # Toplam oyuncu sayısı
        total_players = len(data['team_a']) + len(data['team_b'])
        per_player_cost = float(data['total_cost']) / total_players if total_players > 0 else 0
        
        # A Takımı oyuncularını ekle
        for player_id in data['team_a']:
            mp = MatchPlayer(
                match_id=match.id,
                player_id=player_id,
                team='A',
                payment_amount=per_player_cost,
                has_paid=False
            )
            db.session.add(mp)
        
        # B Takımı oyuncularını ekle
        for player_id in data['team_b']:
            mp = MatchPlayer(
                match_id=match.id,
                player_id=player_id,
                team='B',
                payment_amount=per_player_cost,
                has_paid=False
            )
            db.session.add(mp)
        
        db.session.commit()
        return jsonify({
            "success": True,
            "message": get_translation('match_created'),
            "match_id": match.id
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": f"{get_translation('error')}: {str(e)}"
        }), 400

@app.route('/api/matches/<int:id>', methods=['PUT'])
@admin_required
def update_match_api(id):
    match = Match.query.get_or_404(id)
    data = request.json
    
    try:
        if 'date' in data:
            match.date = datetime.strptime(data['date'], '%Y-%m-%dT%H:%M')  # Datetime format düzeltildi
        if 'location' in data:
            match.location = data['location']
        if 'total_cost' in data:
            match.total_cost = float(data['total_cost'])
        if 'score_team_a' in data:
            match.score_team_a = data['score_team_a']
        if 'score_team_b' in data:
            match.score_team_b = data['score_team_b']
        
        db.session.commit()
        return jsonify({"msg": "Maç başarıyla güncellendi"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/matches/<int:id>', methods=['DELETE'])
@admin_required
def delete_match_api(id):
    try:
        match = Match.query.get_or_404(id)
        
        # Önce maça ait tüm oyuncu kayıtlarını sil
        MatchPlayer.query.filter_by(match_id=id).delete()
        
        # Sonra maçı sil
        db.session.delete(match)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Maç başarıyla silindi"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "Maç silinirken bir hata oluştu: " + str(e)
        }), 500

# Maç detaylarını getirme endpoint'i
@app.route('/api/matches/<int:id>', methods=['GET'])
@admin_required
def get_match_api(id):
    match = Match.query.get_or_404(id)
    return jsonify({
        'id': match.id,
        'date': match.date.strftime('%Y-%m-%dT%H:%M'),  # ISO format
        'location': match.location,
        'total_cost': float(match.total_cost),
        'score_team_a': match.score_team_a,
        'score_team_b': match.score_team_b
    })

@app.route('/api/players/<int:id>', methods=['GET'])
@admin_required
def get_player_api(id):
    try:
        player = Player.query.get_or_404(id)
        return jsonify({
            'success': True,
            'id': player.id,
            'name': player.name,
            'tc_no': player.tc_no,
            'position': player.position
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400

@app.route('/api/matches/<int:id>/teams', methods=['POST'])
@admin_required
def update_match_teams(id):
    try:
        match = Match.get_by_id(id)
        if not match:
            return jsonify({"success": False, "message": "Maç bulunamadı"}), 404
            
        data = request.json
        
        # Takımları güncelle
        match['teams'] = {
            "a": [{
                "player_id": p,
                "has_paid": False,
                "payment_amount": float(match['total_cost']) / (len(data.get('team_a', [])) + len(data.get('team_b', [])))
            } for p in data.get('team_a', [])],
            "b": [{
                "player_id": p,
                "has_paid": False,
                "payment_amount": float(match['total_cost']) / (len(data.get('team_a', [])) + len(data.get('team_b', [])))
            } for p in data.get('team_b', [])]
        }
        
        # MongoDB'de güncelle
        Match.update(id, {"teams": match['teams']})
        
        return jsonify({"success": True, "message": "Takımlar başarıyla güncellendi"})
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/api/matches/<int:match_id>/players/<int:player_id>/payment', methods=['POST'])
@admin_required
def toggle_payment_status(match_id, player_id):
    try:
        match = Match.get_by_id(match_id)
        if not match:
            return jsonify({"success": False, "message": "Maç bulunamadı"}), 404
            
        # Oyuncuyu bul ve ödeme durumunu güncelle
        updated = False
        for team in ['a', 'b']:
            for player in match['teams'][team]:
                if player['player_id'] == str(player_id):
                    player['has_paid'] = not player['has_paid']
                    updated = True
                    break
            if updated:
                break
                
        if not updated:
            return jsonify({"success": False, "message": "Oyuncu bulunamadı"}), 404
            
        # MongoDB'de güncelle
        Match.update(match_id, {"teams": match['teams']})
        
        return jsonify({
            "success": True,
            "message": "Ödeme durumu güncellendi",
            "has_paid": player['has_paid']
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/players/<id>')
def player_profile(id):
    try:
        # Debug için
        print(f"Gelen oyuncu ID: {id}")
        
        # Oyuncuyu bul
        player = Player.get_by_id(id)
        if not player:
            return render_template('404.html',
                                error_message="Oyuncu bulunamadı",
                                error_details=f"ID: {id}"), 404

        # Beğeni/beğenmeme sayılarını al
        reaction_data = reactions.find_one({"player_id": str(player['_id'])}) or {"likes": 0, "dislikes": 0}
        
        # Yorumları al
        player_comments = list(comments.find({"player_id": str(player['_id'])}).sort("created_at", -1))
        
        # Maç istatistiklerini al
        match_stats = Player.get_player_stats(str(player['_id']))

        return render_template('player_profile.html',
                            player=player,
                            stats=match_stats or {},
                            like_count=reaction_data.get('likes', 0),
                            dislike_count=reaction_data.get('dislikes', 0),
                            like_percent=calculate_like_percent(reaction_data),
                            dislike_percent=calculate_dislike_percent(reaction_data),
                            comments=player_comments)

    except Exception as e:
        print(f"Oyuncu profili hatası: {str(e)}")
        return render_template('404.html',
                            error_message="Oyuncu profili yüklenirken hata oluştu",
                            error_details=str(e)), 404

def calculate_like_percent(reaction_data):
    total = reaction_data.get('likes', 0) + reaction_data.get('dislikes', 0)
    if total == 0:
        return 0
    return (reaction_data.get('likes', 0) / total) * 100

def calculate_dislike_percent(reaction_data):
    total = reaction_data.get('likes', 0) + reaction_data.get('dislikes', 0)
    if total == 0:
        return 0
    return (reaction_data.get('dislikes', 0) / total) * 100

@app.route('/new-match', methods=['GET'])
@admin_required
def new_match():
    try:
        # MongoDB'den aktif oyuncuları al ve overall değerlerini hesapla
        all_players = Player.get_all_active()
        
        # Her oyuncu için overall değerini hesapla
        for player in all_players:
            stats = player.get('stats', {})
            weights = {
                'Kaleci': {'pace': 0.1, 'shooting': 0, 'passing': 0.2, 'dribbling': 0.1, 'defending': 0.4, 'physical': 0.2},
                'Defans': {'pace': 0.2, 'shooting': 0.1, 'passing': 0.2, 'dribbling': 0.1, 'defending': 0.3, 'physical': 0.1},
                'Orta Saha': {'pace': 0.15, 'shooting': 0.2, 'passing': 0.25, 'dribbling': 0.2, 'defending': 0.1, 'physical': 0.1},
                'Forvet': {'pace': 0.2, 'shooting': 0.3, 'passing': 0.15, 'dribbling': 0.2, 'defending': 0.05, 'physical': 0.1}
            }
            
            w = weights.get(player.get('position', 'Orta Saha'))
            player['overall'] = int(
                stats.get('pace', 70) * w['pace'] +
                stats.get('shooting', 70) * w['shooting'] +
                stats.get('passing', 70) * w['passing'] +
                stats.get('dribbling', 70) * w['dribbling'] +
                stats.get('defending', 70) * w['defending'] +
                stats.get('physical', 70) * w['physical']
            )
        
        now = datetime.now()
        return render_template('new_match.html', 
                             players=all_players,
                             now=now)
    except Exception as e:
        flash(str(e), 'error')
        return redirect(url_for('matches'))

@app.route('/api/matches', methods=['POST'])
@admin_required
def create_match():
    try:
        data = request.json
        
        # Yeni maç oluştur
        match_data = {
            "date": datetime.strptime(data['date'], '%Y-%m-%dT%H:%M').replace(tzinfo=timezone.utc),  # UTC olarak kaydet
            "location": data['location'],
            "total_cost": float(data['total_cost']),
            "teams": {
                "a": [{"player_id": p, "has_paid": False, "payment_amount": float(data['total_cost']) / (len(data['team_a']) + len(data['team_b']))} for p in data['team_a']],
                "b": [{"player_id": p, "has_paid": False, "payment_amount": float(data['total_cost']) / (len(data['team_a']) + len(data['team_b']))} for p in data['team_b']]
            },
            "score": {
                "team_a": None,
                "team_b": None
            }
        }
        
        # MongoDB'ye kaydet
        match_id = Match.create(match_data)
        
        return jsonify({
            "success": True,
            "match_id": str(match_id)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/set-language/<lang>')
def set_language(lang):
    if lang in ['tr', 'en']:
        session['lang'] = lang
        # Dil değiştiğinde sayfayı yeniden yükle
        return redirect(request.referrer or url_for('index'))
    return redirect(url_for('index'))

@app.context_processor
def inject_language():
    return {
        'current_lang': session.get('lang', 'tr'),
        'available_languages': {
            'tr': 'Türkçe',
            'en': 'English'
        }
    }

def format_date(date, lang='tr'):
    if lang == 'tr':
        return date.strftime('%d/%m/%Y %H:%M')
    return date.strftime('%Y-%m-%d %H:%M')

@app.template_filter('format_date')
def format_date_filter(date):
    return format_date(date, session.get('lang', 'tr'))

@app.route('/api/matches/<int:match_id>/mark-all-paid', methods=['POST'])
@admin_required
def mark_all_paid(match_id):
    try:
        match = Match.get_by_id(str(match_id))
        if not match:
            return jsonify({
                "success": False,
                "message": get_translation('match_not_found')
            }), 404

        # Her iki takımdaki tüm oyuncuları ödenmiş olarak işaretle
        for team in ['a', 'b']:
            for player in match['teams'][team]:
                player['has_paid'] = True

        # Maçı güncelle
        Match.update(str(match_id), {"teams": match['teams']})
        
        return jsonify({
            "success": True,
            "message": get_translation('all_payments_completed')
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"{get_translation('error')}: {str(e)}"
        }), 500

# Dil ayarları için varsayılan Türkçe
@app.before_request
def before_request():
    session['lang'] = 'tr'  # Her zaman Türkçe olacak

@app.route('/static/sounds/<path:filename>')
def serve_sound(filename):
    return send_from_directory('static/sounds', filename)

@app.route('/player-logout')
def player_logout():
    session.pop('player_id', None)
    response = make_response(redirect(url_for('index')))
    response.delete_cookie('player_token')  # player_token'ı sil
    flash('Başarıyla çıkış yaptınız', 'success')
    return response

@app.route('/api/players/<id>/comments', methods=['POST', 'DELETE'])
def manage_comments(id):
    try:
        # Admin kontrolü
        admin_token = request.cookies.get('jwt_token')
        is_admin = False
        if admin_token:
            try:
                jwt.decode(admin_token, app.config['SECRET_KEY'], algorithms=["HS256"])
                is_admin = True
            except:
                pass

        if request.method == 'POST':
            # Yorum ekleme
            if not is_admin and not session.get('player_id'):
                return jsonify({"error": "Yorum yapmak için giriş yapmalısınız"}), 401

            data = request.json
            comment_text = data.get('text')
            
            if not comment_text:
                return jsonify({"error": "Yorum boş olamaz"}), 400

            # Yorumu ekle
            comment = {
                "_id": str(ObjectId()),
                "player_id": id,
                "commenter_id": "admin" if is_admin else session['player_id'],
                "commenter_name": "Admin" if is_admin else Player.get_by_id(session['player_id'])['name'],
                "text": comment_text,
                "created_at": datetime.now(timezone.utc),
                "is_admin": is_admin
            }
            
            db.comments.insert_one(comment)
            comment['created_at'] = comment['created_at'].strftime('%d/%m/%Y %H:%M')
            return jsonify(comment)

        elif request.method == 'DELETE':
            # Yorum silme (sadece admin)
            if not is_admin:
                return jsonify({"error": "Yorum silme yetkisi yok"}), 403

            comment_id = request.args.get('comment_id')
            if not comment_id:
                return jsonify({"error": "Yorum ID'si gerekli"}), 400

            db.comments.delete_one({"_id": comment_id})
            return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/likes/<int:player_id>', methods=['POST'])
def toggle_reaction(player_id):
    # Admin kontrolü
    is_admin = False
    admin_token = request.cookies.get('jwt_token')
    if admin_token:
        try:
            jwt.decode(admin_token, app.config['SECRET_KEY'], algorithms=["HS256"])
            is_admin = True
        except:
            pass

    # Normal oyuncu kontrolü
    if not is_admin and 'player_id' not in session:
        return jsonify({"error": get_translation('login_required_for_reaction')}), 401
    
    try:
        # Beğenen kişinin ID'si (admin veya oyuncu)
        liker_id = -1 if is_admin else session['player_id']
        is_like = request.json.get('is_like', True)
        
        existing_reaction = PlayerLike.query.filter_by(
            player_id=player_id,
            liker_id=liker_id,
            is_admin_reaction=is_admin
        ).first()
        
        if existing_reaction:
            if existing_reaction.is_like == is_like:
                db.session.delete(existing_reaction)
            else:
                existing_reaction.is_like = is_like
        else:
            reaction = PlayerLike(
                player_id=player_id,
                liker_id=liker_id,
                is_like=is_like,
                is_admin_reaction=is_admin
            )
            db.session.add(reaction)
        
        db.session.commit()
        
        # İstatistikleri hesapla
        total_reactions = PlayerLike.query.filter_by(player_id=player_id).count()
        likes = PlayerLike.query.filter_by(player_id=player_id, is_like=True).count()
        dislikes = PlayerLike.query.filter_by(player_id=player_id, is_like=False).count()
        
        like_percent = (likes / total_reactions * 100) if total_reactions > 0 else 0
        dislike_percent = (dislikes / total_reactions * 100) if total_reactions > 0 else 0
        
        return jsonify({
            "success": True,
            "like_percent": like_percent,
            "dislike_percent": dislike_percent,
            "total_reactions": total_reactions
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/admin-logout')
def admin_logout():
    response = make_response(redirect(url_for('index')))
    response.delete_cookie('jwt_token')
    return response

@app.route('/api/matches/<id>/score', methods=['POST'])
@admin_required
def update_match_score(id):
    try:
        data = request.json
        match = Match.get_by_id(id)
        
        if not match:
            return jsonify({"success": False, "message": "Maç bulunamadı"}), 404
            
        match['score'] = {
            'team_a': data['team_a'],
            'team_b': data['team_b']
        }
        
        Match.update(id, {"score": match['score']})
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/matches/<id>/payment', methods=['POST'])
@admin_required
def update_player_payment(id):
    try:
        data = request.json
        match = Match.get_by_id(id)
        
        if not match:
            return jsonify({"success": False, "message": "Maç bulunamadı"}), 404
            
        player_id = data['player_id']
        has_paid = data['has_paid']
        
        # Oyuncuyu bul ve ödeme durumunu güncelle
        for team in ['a', 'b']:
            for player in match['teams'][team]:
                if player['player_id'] == player_id:
                    player['has_paid'] = has_paid
                    break
                    
        Match.update(id, {"teams": match['teams']})
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/matches/<id>/team-payment', methods=['POST'])
@admin_required
def update_team_payments(id):
    try:
        data = request.json
        match = Match.get_by_id(id)
        
        if not match:
            return jsonify({"success": False, "message": "Maç bulunamadı"}), 404
            
        team = data.get('team')
        has_paid = data.get('has_paid')
        
        # Tüm takım oyuncularının ödeme durumunu güncelle
        for player in match['teams'][team]:
            player['has_paid'] = has_paid
            
        Match.update(id, {"teams": match['teams']})
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/matches/<id>')
def match_detail(id):
    try:
        is_admin = bool(request.cookies.get('jwt_token'))
        match = Match.get_by_id(id)
        
        if not match:
            return render_template('404.html',
                                error_message="Maç bulunamadı",
                                error_details=f"ID: {id}"), 404
        
        # Token varsa doğrula
        if is_admin:
            try:
                jwt.decode(request.cookies.get('jwt_token'), 
                         app.config['SECRET_KEY'], 
                         algorithms=["HS256"])
            except:
                is_admin = False
                response = make_response(render_template('match_detail.html', 
                                                      match=match,
                                                      is_admin=False))
                response.delete_cookie('jwt_token')
                return response
        
        return render_template('match_detail.html', 
                             match=match,
                             is_admin=is_admin)
    except Exception as e:
        print(f"Maç detay hatası: {str(e)}")
        return render_template('404.html',
                             error_message="Maç detayı görüntülenirken bir hata oluştu",
                             error_details=str(e)), 404

@app.template_filter('get_player_card_class')
def get_player_card_class(overall):
    try:
        overall = int(overall)
        if overall >= 88:
            return 'elite'      # Mor (En üst seviye)
        elif overall >= 82:
            return 'gold'       # Altın (Yüksek seviye)
        elif overall >= 75:
            return 'silver'     # Gümüş (Orta seviye)
        else:
            return 'bronze'     # Bronz (Başlangıç seviye)
    except (TypeError, ValueError):
        return 'bronze'

@app.template_filter('get_stat_class')
def get_stat_class(value):
    try:
        value = int(value)
        if value >= 85:
            return 'high'       # Yeşil (Çok iyi)
        elif value >= 75:
            return 'medium'     # Sarı (İyi)
        else:
            return 'low'        # Kırmızı (Geliştirilmeli)
    except (TypeError, ValueError):
        return 'low'

@app.route('/api/players/<id>/reaction', methods=['POST'])
def add_reaction(id):
    try:
        # Admin kontrolü ekle
        admin_token = request.cookies.get('jwt_token')
        is_admin = False
        if admin_token:
            try:
                jwt.decode(admin_token, app.config['SECRET_KEY'], algorithms=["HS256"])
                is_admin = True
            except:
                pass

        # Normal kullanıcı kontrolü
        if not is_admin and not session.get('player_id'):
            return jsonify({"error": "Beğeni/beğenmeme için giriş yapmalısınız"}), 401

        data = request.json
        is_like = data.get('is_like')
        
        # Admin veya kullanıcı ID'sini belirle
        user_id = "admin" if is_admin else session.get('player_id')
        
        # Reaksiyonu ekle/güncelle
        success = Player.add_or_update_reaction(id, user_id, is_like, is_admin)
        
        if success:
            reactions = Player.get_reactions(id)
            return jsonify(reactions)
        else:
            return jsonify({"error": "Beğeni eklenemedi"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/players/<id>/reactions/update', methods=['POST'])
def update_reactions(id):
    try:
        # ...
        result = reactions.update_one(
            {"player_id": id},
            {
                "$set": {
                    "likes": likes,
                    "dislikes": dislikes,
                    "updated_at": datetime.now(timezone.utc)  # UTC olarak kaydet
                }
            },
            upsert=True
        )
        # ...

    except Exception as e:
        print(f"Reaksiyon güncelleme hatası: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/players/<id>/update-tc', methods=['POST'])
def update_player_tc(id):
    # Admin kontrolü
    if not is_admin():
        return jsonify({
            "error": "Bu işlem için admin yetkisi gereklidir",
            "redirect_url": url_for('admin_login')
        }), 403
        
    try:
        data = request.json
        new_tc = data.get('tc_no')
        
        if not new_tc:
            return jsonify({"error": "TC kimlik numarası gerekli"}), 400
            
        result = players_collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"tc_no": new_tc}}
        )
        
        if result.modified_count > 0:
            return jsonify({
                "success": True, 
                "message": "TC kimlik numarası güncellendi"
            })
        else:
            return jsonify({
                "error": "Oyuncu bulunamadı veya güncelleme başarısız"
            }), 404
            
    except Exception as e:
        print(f"TC güncelleme hatası: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Health check endpoint'i ekle
@app.route('/health')
def health_check():
    try:
        # MongoDB bağlantısını kontrol et
        client.admin.command('ping')
        return jsonify({"status": "healthy"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', 
                         error_message="İstediğiniz sayfa bulunamadı.",
                         error_details=str(e)), 404

# Static dosyalar için route ekleyin
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# Varsayılan resimler için özel route
@app.route('/static/img/<path:filename>')
def serve_images(filename):
    try:
        return send_from_directory('static/img', filename)
    except:
        # Varsayılan resim bulunamazsa alternatif resim döndür
        if filename == 'default-avatar.png':
            return send_from_directory('static/img', 'placeholder-avatar.png')
        elif filename.startswith('flags/'):
            return send_from_directory('static/img', 'placeholder-flag.png')
        return '', 404

# Dosya yükleme ayarları
UPLOAD_FOLDER = os.path.join('static', 'uploads', 'avatars')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max-size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Dosya uzantı kontrolü
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Cloudinary konfigürasyonu
cloudinary.config(
    cloud_name=Config.CLOUDINARY_CLOUD_NAME,
    api_key=Config.CLOUDINARY_API_KEY,
    api_secret=Config.CLOUDINARY_API_SECRET
)

# Fotoğraf yükleme endpoint'i
@app.route('/api/players/<id>/upload-avatar', methods=['POST'])
@admin_required
def upload_avatar(id):
    try:
        print(f"Fotoğraf yükleme başladı - ID: {id}")
        
        # Oyuncuyu bul
        player = Player.get_by_id(id)
        if not player:
            print(f"Oyuncu bulunamadı: {id}")
            return jsonify({"error": "Oyuncu bulunamadı"}), 404

        print(f"Oyuncu bulundu: {player.get('name')}, ID: {player['_id']}")

        if 'avatar' not in request.files:
            return jsonify({"error": "Dosya seçilmedi"}), 400
            
        file = request.files['avatar']
        if file.filename == '':
            return jsonify({"error": "Dosya seçilmedi"}), 400
            
        if file and allowed_file(file.filename):
            try:
                # Eski avatarı sil
                if player.get('avatar_public_id'):
                    try:
                        print(f"Eski avatar siliniyor: {player['avatar_public_id']}")
                        cloudinary.uploader.destroy(player['avatar_public_id'])
                    except Exception as e:
                        print(f"Eski fotoğraf silinirken hata: {str(e)}")
                
                # Yeni fotoğrafı yükle
                timestamp = int(time.time())
                player_id = player['_id']  # Bulunan oyuncunun ID'sini kullan
                upload_path = f"avatars/player_{player_id}_{timestamp}"
                print(f"Yeni fotoğraf yükleniyor: {upload_path}")
                
                result = cloudinary.uploader.upload(
                    file,
                    folder="avatars",
                    public_id=f"player_{player_id}_{timestamp}",
                    overwrite=True,
                    resource_type="image"
                )
                
                print(f"Cloudinary yanıtı: {result}")
                
                # Veritabanını güncelle - bulunan oyuncunun ID'sini kullan
                if Player.update_avatar(player_id, result):
                    return jsonify({
                        "success": True,
                        "avatar_url": result['secure_url']
                    })
                else:
                    print("Veritabanı güncellenemedi")
                    # Yüklenen fotoğrafı sil
                    cloudinary.uploader.destroy(result['public_id'])
                    return jsonify({"error": "Veritabanı güncellenemedi"}), 500
                    
            except Exception as e:
                print(f"Fotoğraf yükleme hatası: {str(e)}")
                return jsonify({"error": "Fotoğraf yüklenemedi"}), 500
            
        return jsonify({"error": "Geçersiz dosya türü"}), 400
        
    except Exception as e:
        print(f"Fotoğraf yükleme hatası: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Varsayılan avatar'ı indir ve kaydet
def setup_default_avatar():
    default_avatar_path = 'static/img/default-avatar.png'
    if not os.path.exists(default_avatar_path):
        try:
            # Klasörü oluştur
            os.makedirs(os.path.dirname(default_avatar_path), exist_ok=True)
            
            # Varsayılan avatar URL'si
            url = "https://www.gravatar.com/avatar/00000000000000000000000000000000?d=mp&f=y"
            response = requests.get(url, stream=True)
            
            if response.ok:  # status_ok yerine ok kullan
                with open(default_avatar_path, 'wb') as out_file:
                    shutil.copyfileobj(response.raw, out_file)
                print("Varsayılan avatar indirildi")
            else:
                print(f"Avatar indirilemedi: {response.status_code}")
                
        except Exception as e:
            print(f"Varsayılan avatar indirme hatası: {str(e)}")

# Uygulama başlatılırken çağır
setup_default_avatar()

@app.route('/api/debug/db-status')
@admin_required
def db_status():
    try:
        status = {
            "players": [],
            "matches": [],
            "collections": db.list_collection_names()
        }
        
        # Oyuncuları listele
        for player in players_collection.find():
            status["players"].append({
                "_id": str(player["_id"]),
                "name": player.get("name"),
                "id_type": type(player["_id"]).__name__
            })
            
        # Maçları listele
        for match in matches.find():
            status["matches"].append({
                "_id": str(match["_id"]),
                "date": match.get("date"),
                "id_type": type(match["_id"]).__name__
            })
            
        return jsonify(status)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/debug/fix-db')
@admin_required
def fix_database():
    try:
        result = {
            "fixed_players": 0,
            "fixed_matches": 0,
            "errors": []
        }
        
        # Oyuncuları düzelt
        for player in players_collection.find():
            try:
                # ID'yi integer'a çevir
                if isinstance(player['_id'], str):
                    new_id = int(player['_id'])
                    players_collection.update_one(
                        {"_id": player['_id']},
                        {"$set": {"_id": new_id}}
                    )
                    result["fixed_players"] += 1
                
                # Avatar URL'sini kontrol et
                if player.get('avatar_url') and not player.get('avatar_public_id'):
                    # Cloudinary'den public_id çıkar
                    try:
                        public_id = player['avatar_url'].split('/')[-1].split('.')[0]
                        players_collection.update_one(
                            {"_id": player['_id']},
                            {"$set": {"avatar_public_id": f"avatars/{public_id}"}}
                        )
                    except Exception as e:
                        result["errors"].append(f"Avatar fix error for player {player['_id']}: {str(e)}")
                
            except Exception as e:
                result["errors"].append(f"Player fix error {player['_id']}: {str(e)}")
        
        # Maçları düzelt
        for match in matches.find():
            try:
                if isinstance(match['_id'], str):
                    new_id = int(match['_id'])
                    matches.update_one(
                        {"_id": match['_id']},
                        {"$set": {"_id": new_id}}
                    )
                    result["fixed_matches"] += 1
            except Exception as e:
                result["errors"].append(f"Match fix error {match['_id']}: {str(e)}")
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/debug/check-match/<id>')
@admin_required
def check_match(id):
    try:
        # Maçı farklı ID formatlarıyla ara
        results = {
            "original_id": id,
            "found_with": None,
            "match_data": None,
            "id_formats": {
                "as_is": matches.find_one({"_id": id}) is not None,
                "as_string": matches.find_one({"_id": str(id)}) is not None,
                "as_int": matches.find_one({"_id": int(id)}) if str(id).isdigit() else None,
                "as_object_id": matches.find_one({"_id": ObjectId(id)}) if ObjectId.is_valid(id) else None
            }
        }
        
        # Maçı bul
        match = Match.get_by_id(id)
        if match:
            results["found_with"] = "success"
            results["match_data"] = {
                "_id": match["_id"],
                "date": str(match.get("date")),
                "location": match.get("location"),
                "teams": {
                    "a": [{"id": p["player_id"], "name": p.get("name")} for p in match["teams"]["a"]],
                    "b": [{"id": p["player_id"], "name": p.get("name")} for p in match["teams"]["b"]]
                }
            }
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "original_id": id
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080))) 