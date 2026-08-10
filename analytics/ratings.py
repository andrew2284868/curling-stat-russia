import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import sqlite3
import math
from typing import Dict, List, Tuple
from db.database import get_db_connection

def calculate_elo_ratings():
    """
    Computes Elo ratings for all matches and players chronologically.
    Updates player ratings in the database and records history.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    print("[Analytics] Initializing Elo ratings...")
    cursor.execute("UPDATE players SET elo_rating = 1500.0, matches_played = 0, matches_won = 0, matches_lost = 0, win_rate = 0.0")
    cursor.execute("DELETE FROM player_ratings_history")
    conn.commit()

    cursor.execute("SELECT id, elo_rating FROM players")
    player_ratings = {row['id']: float(row['elo_rating']) for row in cursor.fetchall()}
    player_stats = {pid: {"played": 0, "won": 0, "lost": 0} for pid in player_ratings}

    cursor.execute('''
    SELECT m.id as match_id, m.tournament_id, m.tour_name, m.stage_type,
           m.team1_name, m.team2_name, m.team1_id, m.team2_id,
           m.team1_total_score, m.team2_total_score, m.winner_team_id, m.winner_name,
           t.season, t.date_display
    FROM matches m
    JOIN tournaments t ON m.tournament_id = t.id
    WHERE m.team1_total_score IS NOT NULL AND m.team2_total_score IS NOT NULL
    ORDER BY t.season ASC, t.id ASC, m.id ASC
    ''')
    matches = cursor.fetchall()
    print(f"[Analytics] Processing Elo for {len(matches)} finished matches...")

    cursor.execute('''
    SELECT tt.tournament_id, tt.team_display_name, tr.player_id, tr.role
    FROM tournament_teams tt
    JOIN team_rosters tr ON tt.id = tr.tournament_team_id
    ''')
    rosters_cache = {}
    for row in cursor.fetchall():
        key = (row['tournament_id'], row['team_display_name'])
        rosters_cache.setdefault(key, []).append(row['player_id'])

    history_records = []

    for m in matches:
        match_id = m['match_id']
        tourn_id = m['tournament_id']
        t1_name = m['team1_name']
        t2_name = m['team2_name']
        s1 = m['team1_total_score']
        s2 = m['team2_total_score']
        
        p1_list = rosters_cache.get((tourn_id, t1_name), [])
        p2_list = rosters_cache.get((tourn_id, t2_name), [])

        if not p1_list:
            for (tid, tname), pids in rosters_cache.items():
                if tid == tourn_id and (tname in t1_name or t1_name in tname):
                    p1_list = pids
                    break
        if not p2_list:
            for (tid, tname), pids in rosters_cache.items():
                if tid == tourn_id and (tname in t2_name or t2_name in tname):
                    p2_list = pids
                    break

        if not p1_list or not p2_list:
            continue

        r1_avg = sum(player_ratings.get(pid, 1500.0) for pid in p1_list) / len(p1_list)
        r2_avg = sum(player_ratings.get(pid, 1500.0) for pid in p2_list) / len(p2_list)

        e1 = 1.0 / (1.0 + math.pow(10.0, (r2_avg - r1_avg) / 400.0))
        e2 = 1.0 - e1

        if s1 > s2:
            actual1, actual2 = 1.0, 0.0
            for pid in p1_list:
                player_stats[pid]["played"] += 1
                player_stats[pid]["won"] += 1
            for pid in p2_list:
                player_stats[pid]["played"] += 1
                player_stats[pid]["lost"] += 1
        elif s2 > s1:
            actual1, actual2 = 0.0, 1.0
            for pid in p1_list:
                player_stats[pid]["played"] += 1
                player_stats[pid]["lost"] += 1
            for pid in p2_list:
                player_stats[pid]["played"] += 1
                player_stats[pid]["won"] += 1
        else:
            actual1, actual2 = 0.5, 0.5
            for pid in p1_list + p2_list:
                player_stats[pid]["played"] += 1

        stage = m['stage_type']
        if stage in ['final', 'semi', 'playoff']:
            k = 32.0
        else:
            k = 24.0

        point_diff = abs(s1 - s2)
        margin_mult = math.log(point_diff + 1.0) * 0.8 + 0.5 if point_diff > 0 else 1.0
        delta = k * margin_mult * (actual1 - e1)

        for pid in p1_list:
            old_r = player_ratings[pid]
            new_r = max(100.0, old_r + delta)
            player_ratings[pid] = new_r
            history_records.append((pid, tourn_id, match_id, m['date_display'], old_r, new_r, delta))

        for pid in p2_list:
            old_r = player_ratings[pid]
            new_r = max(100.0, old_r - delta)
            player_ratings[pid] = new_r
            history_records.append((pid, tourn_id, match_id, m['date_display'], old_r, new_r, -delta))

    for pid, r in player_ratings.items():
        st = player_stats[pid]
        played = st["played"]
        won = st["won"]
        lost = st["lost"]
        win_rate = (won / played * 100.0) if played > 0 else 0.0
        cursor.execute('''
        UPDATE players
        SET elo_rating = ?, matches_played = ?, matches_won = ?, matches_lost = ?, win_rate = ?
        WHERE id = ?
        ''', (round(r, 1), played, won, lost, round(win_rate, 1), pid))

    if history_records:
        cursor.executemany('''
        INSERT INTO player_ratings_history (player_id, tournament_id, match_id, date, old_rating, new_rating, rating_change)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', history_records)

    conn.commit()
    conn.close()
    print("[Analytics] Elo ratings calculation complete.")
