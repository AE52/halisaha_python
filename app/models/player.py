class Player:
    @staticmethod
    def get_stats(player_id):
        """Oyuncunun maç istatistiklerini hesaplar"""
        from app.models import Match
        
        # Oyuncunun katıldığı tüm maçları bul
        matches_played = []
        total_matches = 0
        wins = 0
        draws = 0
        
        all_matches = Match.get_all()
        for match in all_matches:
            player_found = False
            for team in ['a', 'b']:
                for player in match['teams'][team]:
                    if player['player_id'] == str(player_id):
                        player_found = True
                        total_matches += 1
                        
                        # Galibiyet/beraberlik durumunu kontrol et
                        if match['score']['team_a'] is not None and match['score']['team_b'] is not None:
                            if match['score']['team_a'] == match['score']['team_b']:
                                draws += 1
                            elif (team == 'a' and match['score']['team_a'] > match['score']['team_b']) or \
                                 (team == 'b' and match['score']['team_b'] > match['score']['team_a']):
                                wins += 1
                                
                        # Maç detaylarını ekle
                        matches_played.append({
                            'date': match['date'],
                            'location': match['location'],
                            'score_team_a': match['score']['team_a'],
                            'score_team_b': match['score']['team_b'],
                            'is_winner': (team == 'a' and match['score']['team_a'] > match['score']['team_b']) or \
                                       (team == 'b' and match['score']['team_b'] > match['score']['team_a']),
                            'is_draw': match['score']['team_a'] == match['score']['team_b'],
                            'has_paid': player['has_paid'],
                            'payment_amount': player['payment_amount']
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
            'match_history': matches_played
        } 