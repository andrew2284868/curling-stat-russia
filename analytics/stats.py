import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import sqlite3
from typing import Dict, List
from db.database import get_db_connection
from analytics.ratings import calculate_elo_ratings
from scraper.storage import recalculate_all_medals

def calculate_advanced_end_stats():
    """
    Calculates detailed end metrics for matches, players and teams:
    - Hammer conversion % (scoring 2+ points when holding hammer)
    - Steal rate % (scoring points when NOT holding hammer)
    - Force rate % (holding opponent with hammer to 1 or 0 points)
    - Ends won vs Ends played
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    print("[Analytics] Computing advanced end-level statistics...")

    cursor.execute('''
    SELECT m.id, m.tournament_id, m.team1_name, m.team2_name,
           m.team1_hammer_start, m.team2_hammer_start,
           tt1.id as tt1_id, tt2.id as tt2_id
    FROM matches m
    LEFT JOIN tournament_teams tt1 ON tt1.tournament_id = m.tournament_id AND tt1.team_display_name = m.team1_name
    LEFT JOIN tournament_teams tt2 ON tt2.tournament_id = m.tournament_id AND tt2.team_display_name = m.team2_name
    ''')
    matches = cursor.fetchall()

    cursor.execute('''
    SELECT match_id, end_number, team1_score, team2_score, is_blank
    FROM match_ends
    ORDER BY match_id, end_number ASC
    ''')
    match_ends_cache = {}
    for row in cursor.fetchall():
        match_ends_cache.setdefault(row['match_id'], []).append(row)

    cursor.execute('SELECT tournament_team_id, player_id FROM team_rosters')
    tt_players = {}
    for row in cursor.fetchall():
        tt_players.setdefault(row['tournament_team_id'], []).append(row['player_id'])

    p_stats = {}

    def get_pstat(pid):
        if pid not in p_stats:
            p_stats[pid] = {
                "ends_played": 0,
                "ends_won": 0,
                "hammer_ends": 0,
                "hammer_converted": 0,
                "non_hammer_ends": 0,
                "steals": 0,
                "force_opp_ends": 0,
                "forces": 0
            }
        return p_stats[pid]

    for m in matches:
        m_id = m['id']
        ends = match_ends_cache.get(m_id, [])
        if not ends:
            continue

        p1_list = tt_players.get(m['tt1_id'], [])
        p2_list = tt_players.get(m['tt2_id'], [])

        current_hammer = 1 if m['team1_hammer_start'] == 1 else (2 if m['team2_hammer_start'] == 1 else 2)

        for end in ends:
            s1 = end['team1_score']
            s2 = end['team2_score']
            is_blank = end['is_blank']

            for pid in p1_list:
                get_pstat(pid)["ends_played"] += 1
            for pid in p2_list:
                get_pstat(pid)["ends_played"] += 1

            if s1 > 0:
                for pid in p1_list:
                    get_pstat(pid)["ends_won"] += 1
            elif s2 > 0:
                for pid in p2_list:
                    get_pstat(pid)["ends_won"] += 1

            if current_hammer == 1:
                for pid in p1_list:
                    get_pstat(pid)["hammer_ends"] += 1
                    if s1 >= 2:
                        get_pstat(pid)["hammer_converted"] += 1
                for pid in p2_list:
                    get_pstat(pid)["non_hammer_ends"] += 1
                    get_pstat(pid)["force_opp_ends"] += 1
                    if s2 > 0:
                        get_pstat(pid)["steals"] += 1
                    if s1 <= 1:
                        get_pstat(pid)["forces"] += 1

                if s1 > 0:
                    current_hammer = 2
                elif s2 > 0:
                    current_hammer = 1
            else:
                for pid in p2_list:
                    get_pstat(pid)["hammer_ends"] += 1
                    if s2 >= 2:
                        get_pstat(pid)["hammer_converted"] += 1
                for pid in p1_list:
                    get_pstat(pid)["non_hammer_ends"] += 1
                    get_pstat(pid)["force_opp_ends"] += 1
                    if s1 > 0:
                        get_pstat(pid)["steals"] += 1
                    if s2 <= 1:
                        get_pstat(pid)["forces"] += 1

                if s2 > 0:
                    current_hammer = 1
                elif s1 > 0:
                    current_hammer = 2

    for pid, st in p_stats.items():
        h_conv = (st["hammer_converted"] / st["hammer_ends"] * 100.0) if st["hammer_ends"] > 0 else 0.0
        s_rate = (st["steals"] / st["non_hammer_ends"] * 100.0) if st["non_hammer_ends"] > 0 else 0.0
        f_rate = (st["forces"] / st["force_opp_ends"] * 100.0) if st["force_opp_ends"] > 0 else 0.0

        cursor.execute('''
        UPDATE players
        SET ends_played = ?, ends_won = ?,
            hammer_conversion_rate = ?, steal_rate = ?, force_rate = ?
        WHERE id = ?
        ''', (
            st["ends_played"], st["ends_won"],
            round(h_conv, 1), round(s_rate, 1), round(f_rate, 1),
            pid
        ))

    conn.commit()
    conn.close()
from analytics.ranking_points import calculate_federation_ranking_points

def run_full_analytics():
    """Runs complete analytics pipeline."""
    recalculate_all_medals()
    calculate_elo_ratings()
    calculate_advanced_end_stats()
    calculate_federation_ranking_points()

if __name__ == "__main__":
    run_full_analytics()

