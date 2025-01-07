from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory, make_response
from models import db, Player, Match, MatchPlayer, API_KEY, PlayerComment, PlayerLike
from config import Config
from functools import wraps
from translations import translations
import jwt

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

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

@app.context_processor
def utility_processor():
    return dict(translate=get_translation)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        api_key = data.get('api_key')
        
        if api_key == app.config['ADMIN_API_KEY']:
            # Token oluştur
            token = jwt.encode({
                'admin': True,
                'exp': datetime.utcnow() + timedelta(hours=24)
            }, app.config['SECRET_KEY'])
            
            response = jsonify({'access_token': token})
            # Token'ı cookie olarak da kaydet
            response.set_cookie('jwt_token', token, httponly=True, secure=True)
            return response
        
        return jsonify({'message': 'Geçersiz API anahtarı!'}), 401
    
    return render_template('login.html')

@app.route('/api/players', methods=['POST'])
@admin_required
def add_player_api():
    data = request.json
    try:
        # TC No kontrolü
        if 'tc_no' in data:
            existing_player = Player.query.filter_by(tc_no=data['tc_no']).first()
            if existing_player:
                return jsonify({
                    "success": False,
                    "message": get_translation('tc_exists')
                }), 400

        player = Player(
            name=data['name'],
            tc_no=data.get('tc_no'),  # Opsiyonel TC No
            position=data['position'],
            overall=data['overall'],
            pace=data['pace'],
            shooting=data['shooting'],
            passing=data['passing'],
            dribbling=data['dribbling'],
            defending=data['defending'],
            physical=data['physical']
        )
        db.session.add(player)
        db.session.commit()
        return jsonify({"success": True, "message": get_translation('player_added')})
    except Exception as e:
        db.session.rollback()
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
    players = Player.query.filter_by(is_active=True).all()
    return render_template('players.html', players=players)

@app.route('/matches')
def matches():
    matches = Match.query.order_by(Match.date.desc()).all()
    all_players = Player.query.filter_by(is_active=True).all()
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
    match = Match.query.get_or_404(id)
    data = request.json
    
    # Mevcut oyuncuları temizle
    MatchPlayer.query.filter_by(match_id=id).delete()
    
    # A Takımı oyuncularını ekle
    for player_id in data.get('team_a', []):
        mp = MatchPlayer(
            match_id=id,
            player_id=player_id,
            team='A',
            payment_amount=match.total_cost / (len(data.get('team_a', [])) + len(data.get('team_b', [])))
        )
        db.session.add(mp)
    
    # B Takımı oyuncularını ekle
    for player_id in data.get('team_b', []):
        mp = MatchPlayer(
            match_id=id,
            player_id=player_id,
            team='B',
            payment_amount=match.total_cost / (len(data.get('team_a', [])) + len(data.get('team_b', [])))
        )
        db.session.add(mp)
    
    db.session.commit()
    return jsonify({"msg": "Takımlar başarıyla güncellendi"})

@app.template_filter('get_player_card_class')
def get_player_card_class(ovr):
    if ovr >= 85:
        return 'player-special'
    elif ovr >= 80:
        return 'player-gold'
    elif ovr >= 75:
        return 'player-silver'
    else:
        return 'player-bronze'

# Alternatif olarak context processor olarak da ekleyebiliriz
@app.context_processor
def utility_processor():
    def get_player_card_class(ovr):
        if ovr >= 85:
            return 'player-special'
        elif ovr >= 80:
            return 'player-gold'
        elif ovr >= 75:
            return 'player-silver'
        else:
            return 'player-bronze'
    return dict(get_player_card_class=get_player_card_class)

@app.route('/api/matches/<int:match_id>/players/<int:player_id>/payment', methods=['POST'])
@admin_required
def toggle_payment_status(match_id, player_id):
    try:
        match_player = MatchPlayer.query.filter_by(
            match_id=match_id,
            player_id=player_id
        ).first_or_404()
        
        match_player.has_paid = not match_player.has_paid
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Ödeme durumu güncellendi",
            "has_paid": match_player.has_paid
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "Bir hata oluştu: " + str(e)
        }), 500

@app.route('/matches/<int:id>')
def match_detail(id):
    match = Match.query.get_or_404(id)
    
    # Admin kontrolü
    is_admin = False
    token = request.cookies.get('jwt_token') or request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if token:
        try:
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            is_admin = True
        except:
            is_admin = False
    
    return render_template('match_detail.html', 
                         match=match,
                         is_admin=is_admin,  # Template'e admin durumunu gönder
                         now=datetime.now())

@app.route('/new-match')
@admin_required
def new_match():
    all_players = Player.query.filter_by(is_active=True).all()
    now = datetime.now()
    # Dakikayı 30'un katlarına yuvarlama
    if now.minute % 30:
        now = now + timedelta(minutes=30 - now.minute % 30)
    now = now.replace(second=0, microsecond=0)
    return render_template('new_match.html', all_players=all_players, now=now)

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

@app.route('/player/<int:id>')
def player_profile(id):
    player = Player.query.get_or_404(id)
    
    # Oyuncunun maç istatistiklerini hesapla
    match_players = MatchPlayer.query.filter_by(player_id=id).all()
    total_matches = len(match_players)
    wins = 0
    draws = 0
    match_history = []
    
    for mp in match_players:
        match = Match.query.get(mp.match_id)
        is_winner = False
        is_draw = False
        
        if match.score_team_a is not None and match.score_team_b is not None:
            if match.score_team_a == match.score_team_b:
                is_draw = True
                draws += 1
            else:
                if mp.team == 'A':
                    is_winner = match.score_team_a > match.score_team_b
                else:
                    is_winner = match.score_team_b > match.score_team_a
                
                if is_winner:
                    wins += 1
        
        match_history.append({
            'match_id': match.id,
            'date': match.date,
            'location': match.location,
            'score_team_a': match.score_team_a,
            'score_team_b': match.score_team_b,
            'is_winner': is_winner,
            'is_draw': is_draw,
            'has_paid': mp.has_paid,
            'payment_amount': mp.payment_amount
        })
    
    # İstatistikleri hesapla
    stats = {
        'total_matches': total_matches,
        'wins': wins,
        'draws': draws,
        'losses': total_matches - wins - draws,
        'win_rate': (wins / total_matches * 100) if total_matches > 0 else 0
    }
    
    # Ödeme istatistiklerini hesapla
    payment_stats = {
        'total_debt': sum(mp.payment_amount for mp in match_players),
        'total_paid': sum(mp.payment_amount for mp in match_players if mp.has_paid),
        'remaining': sum(mp.payment_amount for mp in match_players if not mp.has_paid)
    }
    
    # Grafik verilerini hazırla
    chart_data = {
        'labels': [],
        'win_rates': []
    }
    
    win_count = 0
    for i, mp in enumerate(match_players, 1):
        match = Match.query.get(mp.match_id)
        if match.score_team_a is not None and match.score_team_b is not None:
            if mp.team == 'A':
                if match.score_team_a > match.score_team_b:
                    win_count += 1
            else:
                if match.score_team_b > match.score_team_a:
                    win_count += 1
                    
            chart_data['labels'].append(match.date.strftime('%d/%m'))
            chart_data['win_rates'].append(round(win_count / i * 100, 1))
    
    # Admin kontrolü
    is_admin = False
    admin_token = request.cookies.get('jwt_token')
    if admin_token:
        try:
            jwt.decode(admin_token, app.config['SECRET_KEY'], algorithms=["HS256"])
            is_admin = True
        except:
            pass

    # Oyuncu girişi kontrolü
    is_logged_in = 'player_id' in session
    
    # Giriş yapmış kullanıcı bu oyuncuyu beğenmiş mi?
    has_liked = False
    if 'player_id' in session:
        has_liked = PlayerLike.query.filter_by(
            player_id=id,
            liker_id=session['player_id']
        ).first() is not None
    
    return render_template('player_profile.html',
                         player=player,
                         stats=stats,
                         match_history=match_history,
                         payment_stats=payment_stats,
                         chart_data=chart_data,
                         is_admin=is_admin,
                         is_logged_in=is_logged_in,
                         has_liked=has_liked)

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
        # Maça ait tüm oyuncuların ödeme durumunu güncelle
        match_players = MatchPlayer.query.filter_by(match_id=match_id).all()
        
        for mp in match_players:
            mp.has_paid = True
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": get_translation('all_payments_completed')
        })
    except Exception as e:
        db.session.rollback()
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
    if request.method == 'POST':
        tc_no = request.form.get('tc_no')
        player = Player.query.filter_by(tc_no=tc_no).first()
        
        if player:
            # JWT token oluştur
            token = jwt.encode({
                'player_id': player.id,
                'exp': datetime.utcnow() + timedelta(days=30)  # 30 gün geçerli
            }, app.config['SECRET_KEY'])
            
            # Session'a player_id'yi kaydet
            session['player_id'] = player.id
            
            # Response oluştur ve cookie ekle
            response = make_response(redirect(url_for('player_profile', id=player.id)))
            response.set_cookie('player_jwt', token, httponly=True, secure=True)
            
            return response
        else:
            flash(get_translation('invalid_tc'), 'error')
            return redirect(url_for('player_login'))
    
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

if __name__ == '__main__':
    app.run(debug=True) 