import re
from typing import Dict, Any, Tuple
from db.database import get_db_connection

# Tournament Tier definitions
TIER_1_CHAMPIONSHIP_A = "tier_1_championship_a"     # Чемпионат России Группа А (2500 pts) - Главный старт страны
TIER_2_JUNIOR_U22 = "tier_2_junior_u22"             # Первенство России до 22 лет (1200 pts) - Главный молодежный старт
TIER_3_SUPERLEAGUE_U19 = "tier_3_superleague_u19"   # Женская Суперлига, ЧР Группа Б, ПР U19, Спартакиада (500 pts)
TIER_4_CUP = "tier_4_cup"                           # Кубок России (300 pts)
TIER_5_ALL_RUSSIAN_U17 = "tier_5_all_russian_u17"   # Всероссийские соревнования, ПР U17, Отборы (200 pts)

TIER_BASE_POINTS = {
    TIER_1_CHAMPIONSHIP_A: 2500,
    TIER_2_JUNIOR_U22: 1200,
    TIER_3_SUPERLEAGUE_U19: 500,
    TIER_4_CUP: 300,
    TIER_5_ALL_RUSSIAN_U17: 200
}

TIER_DISPLAY_NAMES = {
    TIER_1_CHAMPIONSHIP_A: "Чемпионат России (Группа А)",
    TIER_2_JUNIOR_U22: "Первенство России U22 (Высший молодежный)",
    TIER_3_SUPERLEAGUE_U19: "Суперлига / Группа Б / Спартакиада / U19",
    TIER_4_CUP: "Кубок России",
    TIER_5_ALL_RUSSIAN_U17: "Всероссийские соревнования / U17"
}

PLACE_COEFFICIENTS_GROUP_A = {
    1: 1.00,
    2: 0.80,
    3: 0.65,
    4: 0.50,
    5: 0.38,
    6: 0.38,
    7: 0.28,
    8: 0.28,
    9: 0.18,
    10: 0.18,
    11: 0.18,
    12: 0.18
}

PLACE_COEFFICIENTS_GROUP_B = {
    13: 1.00, # 1st in Group B (500 pts base)
    14: 0.80, # 2nd in Group B
    15: 0.65, # 3rd in Group B
    16: 0.50, # 4th in Group B
    17: 0.38,
    18: 0.38,
    19: 0.28,
    20: 0.28,
    21: 0.18,
    22: 0.18,
    23: 0.18,
    24: 0.18
}

PLACE_COEFFICIENTS_STANDARD = {
    1: 1.00,
    2: 0.80,
    3: 0.65,
    4: 0.50,
    5: 0.38,
    6: 0.38,
    7: 0.28,
    8: 0.28,
    9: 0.18,
    10: 0.18,
    11: 0.18,
    12: 0.18,
    13: 0.10,
    14: 0.10,
    15: 0.10,
    16: 0.10,
    17: 0.05,
    18: 0.05,
    19: 0.05,
    20: 0.05,
    21: 0.05,
    22: 0.05,
    23: 0.05,
    24: 0.05
}

MATCH_WIN_BONUS = 15.0

def classify_tournament_tier(title: str, discipline: str) -> Tuple[str, str, int]:
    """
    Classifies a tournament into its official Federation Tier, returning:
    (tier_code, tier_display_name, base_points)
    """
    t_low = title.lower()
    
    # 1. Check for Junior U22 Championship (Tier 2 - 1200 pts)
    if ('до 22' in t_low or 'u22' in t_low) and 'первенство россии' in t_low:
        return TIER_2_JUNIOR_U22, TIER_DISPLAY_NAMES[TIER_2_JUNIOR_U22], TIER_BASE_POINTS[TIER_2_JUNIOR_U22]
            
    # 2. Check for Superleague (Tier 3 - 500 pts)
    if 'суперлига' in t_low:
        return TIER_3_SUPERLEAGUE_U19, TIER_DISPLAY_NAMES[TIER_3_SUPERLEAGUE_U19], TIER_BASE_POINTS[TIER_3_SUPERLEAGUE_U19]

    # 3. Check for Junior U19 Championship / Spartakiad (Tier 3 - 500 pts)
    if 'до 19' in t_low or 'u19' in t_low or 'спартакиада' in t_low:
        return TIER_3_SUPERLEAGUE_U19, TIER_DISPLAY_NAMES[TIER_3_SUPERLEAGUE_U19], TIER_BASE_POINTS[TIER_3_SUPERLEAGUE_U19]
        
    # 4. Check for Russian Championship (Adult - Tier 1 - 2500 pts)
    if 'чемпионат россии' in t_low:
        return TIER_1_CHAMPIONSHIP_A, TIER_DISPLAY_NAMES[TIER_1_CHAMPIONSHIP_A], TIER_BASE_POINTS[TIER_1_CHAMPIONSHIP_A]

    # 5. Check for Russian Cup (Tier 4 - 300 pts)
    if 'кубок россии' in t_low:
        return TIER_4_CUP, TIER_DISPLAY_NAMES[TIER_4_CUP], TIER_BASE_POINTS[TIER_4_CUP]

    # 6. Check for Youth U17 / All-Russian / Selection tournaments (Tier 5 - 200 pts)
    if 'до 17' in t_low or 'u17' in t_low or 'всероссийские соревнования' in t_low or 'отбор' in t_low:
        return TIER_5_ALL_RUSSIAN_U17, TIER_DISPLAY_NAMES[TIER_5_ALL_RUSSIAN_U17], TIER_BASE_POINTS[TIER_5_ALL_RUSSIAN_U17]
        
    # Default regional / international
    return TIER_5_ALL_RUSSIAN_U17, TIER_DISPLAY_NAMES[TIER_5_ALL_RUSSIAN_U17], TIER_BASE_POINTS[TIER_5_ALL_RUSSIAN_U17]

def calculate_federation_ranking_points():
    """
    Computes official Federation Ranking Points (fcf_points) for all players and teams
    in the database based on tournament tiers, final places (distinguishing Group A vs Group B),
    and match victories, STRICTLY ISOLATING points per discipline.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("[Ranking Points] Calculating Calibrated Federation Ranking Points...")
    
    # 1. Update tournament tier metadata
    cursor.execute("SELECT id, title, discipline FROM tournaments")
    tournaments = cursor.fetchall()
    
    tourn_tier_map = {}
    for t in tournaments:
        t_id = t['id']
        title = t['title']
        disc = t['discipline']
        t_code, t_name, base_pts = classify_tournament_tier(title, disc)
        
        is_split_championship = ('чемпионат россии' in title.lower()) and (disc in ['classic_men', 'classic_women'])
        is_split_junior = ('первенство россии' in title.lower()) and ('до 22' in title.lower())
        
        tourn_tier_map[t_id] = {
            "title": title,
            "discipline": disc,
            "tier_code": t_code,
            "tier_name": t_name,
            "base_points": base_pts,
            "is_split_championship": is_split_championship,
            "is_split_junior": is_split_junior
        }
        
    # 2. Compute team-level and player-level tournament points strictly per discipline
    cursor.execute('''
    SELECT tt.id, tt.tournament_id, tt.team_id, tt.team_display_name, tt.skip_name, tt.final_place
    FROM tournament_teams tt
    ''')
    tourn_teams = cursor.fetchall()
    
    cursor.execute('''
    SELECT tournament_id, team1_name, team2_name, winner_name
    FROM matches
    WHERE is_finished = 1 AND winner_name IS NOT NULL AND winner_name != ''
    ''')
    match_rows = cursor.fetchall()
    
    team_tourn_wins = {}
    for m in match_rows:
        t_id = m['tournament_id']
        w_name = m['winner_name']
        key = (t_id, w_name)
        team_tourn_wins[key] = team_tourn_wins.get(key, 0) + 1

    player_disc_stats = {}
    player_total_points = {}
    team_disc_points = {} # (team_id, discipline) -> points
    
    # Preload rosters with roles
    cursor.execute('SELECT tournament_team_id, player_id, role FROM team_rosters')
    rosters_map = {}
    for r in cursor.fetchall():
        rosters_map.setdefault(r['tournament_team_id'], []).append((r['player_id'], r['role']))
        
    for tt in tourn_teams:
        tt_id = tt['id']
        t_id = tt['tournament_id']
        team_id = tt['team_id']
        team_name = tt['team_display_name']
        place = tt['final_place']
        
        t_info = tourn_tier_map.get(t_id, {
            "title": "",
            "discipline": "classic_general",
            "tier_code": TIER_5_ALL_RUSSIAN_U17,
            "tier_name": TIER_DISPLAY_NAMES[TIER_5_ALL_RUSSIAN_U17],
            "base_points": 200,
            "is_split_championship": False,
            "is_split_junior": False
        })
        
        base_pts = t_info["base_points"]
        disc = t_info["discipline"]
        
        # Calculate place points based on Group A vs Group B
        if t_info["is_split_championship"]:
            if place and place <= 12:
                coeff = PLACE_COEFFICIENTS_GROUP_A.get(place, 0.18)
                place_points = 2500 * coeff
            elif place and place > 12:
                coeff = PLACE_COEFFICIENTS_GROUP_B.get(place, 0.10)
                place_points = 500 * coeff
            else:
                place_points = 0.0
        elif t_info["is_split_junior"]:
            if place and place <= 12:
                coeff = PLACE_COEFFICIENTS_GROUP_A.get(place, 0.18)
                place_points = 1200 * coeff
            elif place and place > 12:
                coeff = PLACE_COEFFICIENTS_GROUP_B.get(place, 0.10)
                place_points = 300 * coeff
            else:
                place_points = 0.0
        else:
            coeff = PLACE_COEFFICIENTS_STANDARD.get(place, 0.05 if place and place > 24 else 0.0)
            place_points = base_pts * coeff
        
        wins = team_tourn_wins.get((t_id, team_name), 0)
        win_bonus = wins * MATCH_WIN_BONUS
        
        earned_points = round(place_points + win_bonus, 1)
        
        if team_id:
            t_disc_key = (team_id, disc)
            team_disc_points[t_disc_key] = team_disc_points.get(t_disc_key, 0.0) + earned_points
            
        # Distribute to players strictly inside this discipline
        roster_entries = rosters_map.get(tt_id, [])
        for pid, role in roster_entries:
            player_total_points[pid] = player_total_points.get(pid, 0.0) + earned_points
            
            # Discipline specific stats
            disc_key = (pid, disc)
            if disc_key not in player_disc_stats:
                player_disc_stats[disc_key] = {
                    "fcf_points": 0.0,
                    "matches_played": 0,
                    "matches_won": 0,
                    "matches_lost": 0,
                    "gold_medals": 0,
                    "silver_medals": 0,
                    "bronze_medals": 0,
                    "is_skip": 0
                }
            
            player_disc_stats[disc_key]["fcf_points"] += earned_points
            if role == 'skip':
                player_disc_stats[disc_key]["is_skip"] = 1
                
            if place == 1:
                player_disc_stats[disc_key]["gold_medals"] += 1
            elif place == 2:
                player_disc_stats[disc_key]["silver_medals"] += 1
            elif place == 3:
                player_disc_stats[disc_key]["bronze_medals"] += 1

    # 3. Calculate match wins/losses per player per discipline
    cursor.execute('''
    SELECT tr.player_id, t.discipline,
           COUNT(DISTINCT m.id) as played,
           SUM(CASE WHEN m.winner_name = tt.team_display_name THEN 1 ELSE 0 END) as won
    FROM team_rosters tr
    JOIN tournament_teams tt ON tr.tournament_team_id = tt.id
    JOIN tournaments t ON tt.tournament_id = t.id
    JOIN matches m ON m.tournament_id = t.id AND (m.team1_name = tt.team_display_name OR m.team2_name = tt.team_display_name)
    WHERE m.is_finished = 1
    GROUP BY tr.player_id, t.discipline
    ''')
    for row in cursor.fetchall():
        pid = row['player_id']
        disc = row['discipline']
        played = row['played'] or 0
        won = row['won'] or 0
        lost = played - won
        
        disc_key = (pid, disc)
        if disc_key not in player_disc_stats:
            player_disc_stats[disc_key] = {
                "fcf_points": 0.0,
                "matches_played": 0,
                "matches_won": 0,
                "matches_lost": 0,
                "gold_medals": 0,
                "silver_medals": 0,
                "bronze_medals": 0,
                "is_skip": 0
            }
        player_disc_stats[disc_key]["matches_played"] = played
        player_disc_stats[disc_key]["matches_won"] = won
        player_disc_stats[disc_key]["matches_lost"] = lost

    # 4. Save to player_discipline_stats table
    cursor.execute("DELETE FROM player_discipline_stats")
    
    cursor.execute("SELECT id, elo_rating FROM players")
    player_elos = {r['id']: r['elo_rating'] for r in cursor.fetchall()}
    
    for (pid, disc), st in player_disc_stats.items():
        played = st["matches_played"]
        won = st["matches_won"]
        lost = st["matches_lost"]
        win_rate = round(won / played * 100.0, 1) if played > 0 else 0.0
        elo = player_elos.get(pid, 1500.0)
        
        cursor.execute('''
        INSERT INTO player_discipline_stats (
            player_id, discipline, fcf_points, elo_rating,
            matches_played, matches_won, matches_lost, win_rate,
            gold_medals, silver_medals, bronze_medals, is_skip
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            pid, disc, round(st["fcf_points"], 1), elo,
            played, won, lost, win_rate,
            st["gold_medals"], st["silver_medals"], st["bronze_medals"],
            st["is_skip"]
        ))
        
    # 5. Update tournaments metadata in DB
    for t_id, t_info in tourn_tier_map.items():
        cursor.execute('''
        UPDATE tournaments
        SET tier = ?, tier_name = ?, base_points = ?
        WHERE id = ?
        ''', (t_info['tier_code'], t_info['tier_name'], t_info['base_points'], t_id))
        
    # 6. Update overall players fcf_points
    cursor.execute("UPDATE players SET fcf_points = 0.0")
    for pid, pts in player_total_points.items():
        cursor.execute("UPDATE players SET fcf_points = ? WHERE id = ?", (pts, pid))
        
    # 7. Update teams points and accurately assign highest-tier skip for each team
    cursor.execute("UPDATE teams SET fcf_points = 0.0")
    for (tid, disc), pts in team_disc_points.items():
        cursor.execute("UPDATE teams SET fcf_points = ? WHERE id = ?", (pts, tid))
        
    cursor.execute("SELECT id, discipline FROM teams")
    all_teams = cursor.fetchall()
    for t_row in all_teams:
        t_db_id = t_row['id']
        cursor.execute('''
        SELECT tt.skip_name
        FROM tournament_teams tt
        JOIN tournaments t ON tt.tournament_id = t.id
        WHERE tt.team_id = ? AND tt.skip_name IS NOT NULL AND tt.skip_name != ''
        ORDER BY t.base_points DESC, (tt.final_place IS NULL), tt.final_place ASC
        LIMIT 1
        ''', (t_db_id,))
        best_skip_row = cursor.fetchone()
        if best_skip_row and best_skip_row[0]:
            cursor.execute("UPDATE teams SET skip_name = ? WHERE id = ?", (best_skip_row[0], t_db_id))

    conn.commit()
    conn.close()
    print(f"[Ranking Points] Successfully updated calibrated rankings for {len(player_disc_stats)} player-discipline pairs.")
