from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory, make_response
from models import Player, Match, API_KEY  # MatchPlayer ve diğer modelleri kaldır
from config import Config
from functools import wraps
from translations import translations
import jwt

app = Flask(__name__)
app.config.from_object(Config)

# Decorator'ları en başa alalım
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        # Token'ı header'dan al
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                pass
        
        # Cookie'den token kontrolü
        if not token:
            token = request.cookies.get('jwt_token')
        
        if not token:
            # API isteği ise JSON yanıt döndür
            if request.path.startswith('/api/'):
                return jsonify({'message': 'Token bulunamadı!'}), 401
            # Normal sayfa isteği ise login'e yönlendir
            return redirect(url_for('login'))

        try:
            # Token'ı doğrula
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            if request.path.startswith('/api/'):
                return jsonify({'message': 'Token süresi doldu!'}), 401
            return redirect(url_for('login'))
        except jwt.InvalidTokenError:
            if request.path.startswith('/api/'):
                return jsonify({'message': 'Geçersiz token!'}), 401
            return redirect(url_for('login'))
            
    return decorated_function

def player_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('player_jwt')
        
        if not token:
            flash(get_translation('login_required'), 'error')
            return redirect(url_for('player_login'))

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            if 'player_id' not in data:
                raise jwt.InvalidTokenError
                
            # Session'ı güncelle
            session['player_id'] = data['player_id']
            return f(*args, **kwargs)
            
        except jwt.ExpiredSignatureError:
            flash(get_translation('session_expired'), 'error')
            return redirect(url_for('player_login'))
        except jwt.InvalidTokenError:
            flash(get_translation('invalid_session'), 'error')
            return redirect(url_for('player_login'))
            
    return decorated_function

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
    if overall >= 85:
        return 'elite'
    elif overall >= 75:
        return 'gold'
    elif overall >= 65:
        return 'silver'
    else:
        return 'bronze'

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
        get_player_info=get_player_info
    )

def get_stat_class(value):
    try:
        value = int(value)
        if value >= 85:
            return 'stat-high'
        elif value >= 70:
            return 'stat-medium'
        else:
            return 'stat-low'
    except (TypeError, ValueError):
        return 'stat-low'  # Varsayılan değer

def get_player_card_class(overall):
    try:
        overall = int(overall)
        if overall >= 85:
            return 'elite'
        elif overall >= 75:
            return 'gold'
        elif overall >= 65:
            return 'silver'
        else:
            return 'bronze'
    except (TypeError, ValueError):
        return 'bronze'  # Varsayılan değer

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Oyuncu girişi yapılmışsa admin girişine izin verme
    if 'player_id' in session:
        flash(get_translation('player_already_logged_in'), 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        data = request.get_json()
        api_key = data.get('api_key')
        
        if api_key == app.config['ADMIN_API_KEY']:
            token = jwt.encode({
                'admin': True,
                'exp': datetime.utcnow() + timedelta(hours=24)
            }, app.config['SECRET_KEY'])
            
            response = jsonify({'access_token': token})
            response.set_cookie('jwt_token', token, httponly=True, secure=True)
            return response
        
        return jsonify({'message': get_translation('invalid_api_key')}), 401
    
    return render_template('login.html')

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
        players.insert_one(player_data)
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
        # MongoDB'den aktif oyuncuları al
        players_list = Player.get_all_active()
        
        # Her oyuncu için overall değerini hesapla
        for player in players_list:
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
            
            # Stats değerlerini direkt olarak player objesine ekle
            player['stats'] = {
                'pace': stats.get('pace', 70),
                'shooting': stats.get('shooting', 70),
                'passing': stats.get('passing', 70),
                'dribbling': stats.get('dribbling', 70),
                'defending': stats.get('defending', 70),
                'physical': stats.get('physical', 70)
            }
            
        return render_template('players.html', players=players_list)
    except Exception as e:
        flash(str(e), 'error')
        return redirect(url_for('index'))

@app.route('/matches')
def matches():
    matches = Match.get_all()
    all_players = Player.get_all_active()
    return render_template('matches.html', 
                         matches=matches, 
                         all_players=all_players,
                         now=datetime.now())

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
    player = Player.get_by_id(id)
    if not player:
        flash('Oyuncu bulunamadı', 'error')
        return redirect(url_for('players'))
    
    # İstatistikleri hesapla
    stats = Player.get_stats(id)
    
    # Beğeni ve yorum istatistiklerini hesapla
    reactions = Player.get_reactions(id)
    total_reactions = reactions['likes'] + reactions['dislikes']
    
    like_percent = (reactions['likes'] / total_reactions * 100) if total_reactions > 0 else 0
    dislike_percent = (reactions['dislikes'] / total_reactions * 100) if total_reactions > 0 else 0
    
    # Admin kontrolü
    is_admin = False
    token = request.cookies.get('jwt_token')
    if token:
        try:
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            is_admin = True
        except:
            pass

    return render_template('player_profile.html',
                         player=player,
                         stats=stats,
                         like_count=reactions['likes'],
                         dislike_count=reactions['dislikes'],
                         like_percent=like_percent,
                         dislike_percent=dislike_percent,
                         current_user_reaction=reactions.get('current_user_reaction'),
                         comments=Player.get_comments(id),
                         is_admin=is_admin)

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
            "date": datetime.strptime(data['date'], '%Y-%m-%dT%H:%M'),
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

@app.route('/player-login', methods=['GET', 'POST'])
def player_login():
    # Admin girişi yapılmışsa oyuncu girişine izin verme
    admin_token = request.cookies.get('jwt_token')
    if admin_token:
        try:
            jwt.decode(admin_token, app.config['SECRET_KEY'], algorithms=["HS256"])
            flash(get_translation('admin_already_logged_in'), 'warning')
            return redirect(url_for('index'))
        except:
            pass
    
    if request.method == 'POST':
        tc_no = request.form.get('tc_no')
        player = Player.get_by_tc(tc_no)
        
        if player:
            token = jwt.encode({
                'player_id': player['_id'],
                'exp': datetime.utcnow() + timedelta(hours=24)
            }, app.config['SECRET_KEY'])
            
            session['player_id'] = player['_id']
            
            response = make_response(redirect(url_for('index')))
            response.set_cookie('player_jwt', token, httponly=True, secure=True)
            return response
        else:
            flash(get_translation('invalid_tc'), 'error')
    
    return render_template('player_login.html')

@app.route('/player-logout')
def player_logout():
    session.pop('player_id', None)
    response = make_response(redirect(url_for('index')))
    response.delete_cookie('player_jwt')
    return response

@app.route('/api/comments/<int:player_id>', methods=['POST'])
def add_comment(player_id):
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
        return jsonify({"error": get_translation('login_required_for_comment')}), 401
    
    try:
        # Yorum yapan kişinin ID'si (admin veya oyuncu)
        commenter_id = None
        if is_admin:
            commenter_id = -1  # Admin için özel ID
        else:
            commenter_id = session['player_id']
        
        comment_text = request.json.get('comment')
        if not comment_text:
            return jsonify({"error": "Yorum boş olamaz"}), 400
        
        comment = PlayerComment(
            player_id=player_id,
            commenter_id=commenter_id,
            comment=comment_text,
            is_admin_comment=is_admin
        )
        db.session.add(comment)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Yorum başarıyla eklendi"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

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
    match = Match.get_by_id(id)
    if not match:
        flash('Maç bulunamadı', 'error')
        return redirect(url_for('matches'))
        
    return render_template('match_detail.html', match=match)

if __name__ == '__main__':
    app.run(debug=True) 