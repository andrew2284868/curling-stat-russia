import sqlite3
import json
import re
import threading
from typing import Dict, Any, List
from db.database import get_db_connection
from scraper.extractor import clean_text, canonical_russian_name, is_valid_person_name, is_foreign_team, ALL_FIRST_NAMES, MALE_FIRST_NAMES, FEMALE_FIRST_NAMES

db_write_lock = threading.Lock()

def clean_team_name(name: str) -> str:
    name = clean_text(name)
    name = re.sub(r'\(.*?\)', '', name).strip()
    name = re.sub(r'\s+(Санкт-Петербург|Москва|Московская область|Краснодарский край|Челябинская область|Новосибирская область)$', '', name, flags=re.IGNORECASE).strip()
    return name

def detect_player_gender(name: str, discipline: str) -> str:
    if 'women' in discipline or 'жен' in discipline:
        return 'F'
    if 'men' in discipline or 'муж' in discipline:
        return 'M'
    
    words = name.lower().split()
    for w in words:
        w_clean = w.replace('ё', 'е')
        if w_clean in FEMALE_FIRST_NAMES:
            return 'F'
        if w_clean in MALE_FIRST_NAMES:
            return 'M'
        if w_clean.endswith(('ова', 'ева', 'ина', 'ая', 'яя')):
            return 'F'
        if w_clean.endswith(('ов', 'ев', 'ин', 'ый', 'ий')):
            return 'M'
    return 'M'

def save_tournament_data(data: Dict[str, Any], raw_html: str = "") -> int:
    with db_write_lock:
        conn = get_db_connection()
        cursor = conn.cursor()

        url = data['url']
        title = data['title']
        season = data['season']
        date_display = data.get('date_display', '')
        discipline = data.get('discipline', 'classic_general')
        category = data.get('category', 'other')
        gender_age = data.get('gender_age', 'general')
        pdf_links_json = json.dumps(data.get('pdf_links', []), ensure_ascii=False)

        cursor.execute('''
        INSERT INTO tournaments (url, title, season, date_display, discipline, category, gender_age, pdf_links_json, raw_html)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title = excluded.title,
            season = excluded.season,
            date_display = excluded.date_display,
            discipline = excluded.discipline,
            category = excluded.category,
            gender_age = excluded.gender_age,
            pdf_links_json = excluded.pdf_links_json,
            raw_html = excluded.raw_html
        ''', (url, title, season, date_display, discipline, category, gender_age, pdf_links_json, raw_html))
        
        cursor.execute('SELECT id FROM tournaments WHERE url = ?', (url,))
        tournament_id = cursor.fetchone()[0]

        team_name_to_id = {}
        team_display_to_ttid = {}
        
        # 1. Process Rosters
        for r in data.get('rosters', []):
            raw_team_name = clean_text(r['team_name'])
            c_team_name = clean_team_name(raw_team_name)
            raw_skip = r.get('skip', '')
            skip_name = canonical_russian_name(raw_skip) if is_valid_person_name(raw_skip) else ""
            coach = r.get('coach', '')
            is_f = 1 if is_foreign_team(raw_team_name) else 0

            cursor.execute('''
            INSERT INTO teams (name, clean_name, skip_name, discipline, category)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(clean_name, discipline) DO UPDATE SET
                name = excluded.name,
                skip_name = CASE WHEN excluded.skip_name != '' THEN excluded.skip_name ELSE teams.skip_name END
            ''', (raw_team_name, c_team_name, skip_name, discipline, category))

            cursor.execute('SELECT id FROM teams WHERE clean_name = ? AND discipline = ?', (c_team_name, discipline))
            team_id = cursor.fetchone()[0]
            team_name_to_id[c_team_name] = team_id
            team_name_to_id[raw_team_name] = team_id

            cursor.execute('''
            INSERT INTO tournament_teams (tournament_id, team_id, team_display_name, skip_name, coach)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(tournament_id, team_display_name) DO UPDATE SET
                coach = excluded.coach,
                skip_name = CASE WHEN excluded.skip_name != '' THEN excluded.skip_name ELSE tournament_teams.skip_name END
            ''', (tournament_id, team_id, raw_team_name, skip_name, coach))

            cursor.execute('SELECT id FROM tournament_teams WHERE tournament_id = ? AND team_display_name = ?', (tournament_id, raw_team_name))
            tourn_team_id = cursor.fetchone()[0]
            team_display_to_ttid[raw_team_name] = tourn_team_id
            team_display_to_ttid[c_team_name] = tourn_team_id

            # If foreign team, do not insert into Russian players leaderboard
            if is_f:
                continue

            roster_player_ids = []
            for order_idx, p_info in enumerate(r.get('players', [])):
                if isinstance(p_info, dict):
                    p_name = p_info.get('name', '')
                    p_role = p_info.get('role', 'player')
                else:
                    p_name = str(p_info)
                    p_role = 'player'

                norm_name = canonical_russian_name(p_name)
                if not is_valid_person_name(norm_name):
                    continue

                gender = detect_player_gender(norm_name, discipline)

                cursor.execute('''
                INSERT INTO players (full_name, normalized_name, gender)
                VALUES (?, ?, ?)
                ON CONFLICT(full_name) DO UPDATE SET
                    gender = CASE WHEN excluded.gender IS NOT NULL THEN excluded.gender ELSE players.gender END
                ''', (norm_name, norm_name, gender))

                cursor.execute('SELECT id FROM players WHERE full_name = ?', (norm_name,))
                player_id = cursor.fetchone()[0]
                roster_player_ids.append((player_id, norm_name, p_role))

                cursor.execute('''
                INSERT INTO team_rosters (tournament_team_id, player_id, role, order_index)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(tournament_team_id, player_id) DO UPDATE SET
                    role = excluded.role,
                    order_index = excluded.order_index
                ''', (tourn_team_id, player_id, p_role, order_idx))

            # If skip wasn't set, find player with role 'skip'
            if not skip_name:
                for pid, pname, prole in roster_player_ids:
                    if prole == 'skip':
                        skip_name = pname
                        cursor.execute('UPDATE tournament_teams SET skip_name = ? WHERE id = ?', (skip_name, tourn_team_id))
                        cursor.execute('UPDATE teams SET skip_name = ? WHERE id = ?', (skip_name, team_id))
                        break

        # 2. Process Standings (and roster_players if embedded)
        for st in data.get('standings', []):
            raw_team_name = clean_text(st['team_name'])
            c_team_name = clean_team_name(raw_team_name)
            place = st.get('place')
            place_text = st.get('place_text', str(place) if place else "")
            raw_skip = st.get('skip_name', '')
            skip_name = canonical_russian_name(raw_skip) if is_valid_person_name(raw_skip) else ""

            cursor.execute('''
            INSERT INTO teams (name, clean_name, skip_name, discipline, category)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(clean_name, discipline) DO UPDATE SET
                name = excluded.name,
                skip_name = CASE WHEN excluded.skip_name != '' THEN excluded.skip_name ELSE teams.skip_name END
            ''', (raw_team_name, c_team_name, skip_name, discipline, category))

            cursor.execute('SELECT id FROM teams WHERE clean_name = ? AND discipline = ?', (c_team_name, discipline))
            team_id = cursor.fetchone()[0]
            team_name_to_id[c_team_name] = team_id
            team_name_to_id[raw_team_name] = team_id

            cursor.execute('''
            INSERT INTO tournament_teams (tournament_id, team_id, team_display_name, skip_name, final_place, place_text)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tournament_id, team_display_name) DO UPDATE SET
                final_place = excluded.final_place,
                place_text = excluded.place_text,
                skip_name = CASE WHEN excluded.skip_name != '' THEN excluded.skip_name ELSE tournament_teams.skip_name END
            ''', (tournament_id, team_id, raw_team_name, skip_name, place, place_text))

            cursor.execute('SELECT id FROM tournament_teams WHERE tournament_id = ? AND team_display_name = ?', (tournament_id, raw_team_name))
            tourn_team_id = cursor.fetchone()[0]
            team_display_to_ttid[raw_team_name] = tourn_team_id
            team_display_to_ttid[c_team_name] = tourn_team_id

            # If standing has roster_players (e.g. Russian Championship Table 1), add them!
            roster_players = st.get('roster_players', [])
            for order_idx, p_name in enumerate(roster_players):
                norm_name = canonical_russian_name(p_name)
                if not is_valid_person_name(norm_name):
                    continue

                gender = detect_player_gender(norm_name, discipline)
                cursor.execute('''
                INSERT INTO players (full_name, normalized_name, gender)
                VALUES (?, ?, ?)
                ON CONFLICT(full_name) DO NOTHING
                ''', (norm_name, norm_name, gender))

                cursor.execute('SELECT id FROM players WHERE full_name = ?', (norm_name,))
                player_id = cursor.fetchone()[0]

                p_role = "skip" if skip_name and (skip_name in norm_name or norm_name in skip_name) else "player"

                cursor.execute('''
                INSERT INTO team_rosters (tournament_team_id, player_id, role, order_index)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(tournament_team_id, player_id) DO UPDATE SET
                    role = excluded.role,
                    order_index = excluded.order_index
                ''', (tourn_team_id, player_id, p_role, order_idx))

        # 3. Process Matches
        cursor.execute('DELETE FROM matches WHERE tournament_id = ?', (tournament_id,))

        for m in data.get('matches', []):
            t1_name = clean_text(m['team1_name'])
            t2_name = clean_text(m['team2_name'])
            c_t1 = clean_team_name(t1_name)
            c_t2 = clean_team_name(t2_name)

            t1_id = team_name_to_id.get(c_t1) or team_name_to_id.get(t1_name)
            t2_id = team_name_to_id.get(c_t2) or team_name_to_id.get(t2_name)

            t1_skip = m.get('team1_skip', '')
            t2_skip = m.get('team2_skip', '')

            winner_id = None
            if m.get('winner_name') == t1_name or (m.get('team1_total_score') is not None and m.get('team2_total_score') is not None and m['team1_total_score'] > m['team2_total_score']):
                winner_id = t1_id
                winner_name = t1_name
            elif m.get('winner_name') == t2_name or (m.get('team1_total_score') is not None and m.get('team2_total_score') is not None and m['team2_total_score'] > m['team1_total_score']):
                winner_id = t2_id
                winner_name = t2_name
            else:
                winner_name = m.get('winner_name')

            cursor.execute('''
            INSERT INTO matches (
                tournament_id, tour_name, stage_type, match_identifier,
                team1_name, team2_name, team1_id, team2_id,
                team1_skip, team2_skip,
                team1_hammer_start, team2_hammer_start,
                team1_total_score, team2_total_score,
                winner_team_id, winner_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                tournament_id, m.get('tour_name', 'Матчи'), m.get('stage_type', 'group'), m.get('match_identifier', ''),
                t1_name, t2_name, t1_id, t2_id,
                t1_skip, t2_skip,
                m.get('team1_hammer_start', 0), m.get('team2_hammer_start', 0),
                m.get('team1_total_score'), m.get('team2_total_score'),
                winner_id, winner_name
            ))
            
            match_id = cursor.lastrowid

            for end_info in m.get('ends', []):
                cursor.execute('''
                INSERT INTO match_ends (match_id, end_number, team1_score, team2_score, is_blank)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(match_id, end_number) DO UPDATE SET
                    team1_score = excluded.team1_score,
                    team2_score = excluded.team2_score,
                    is_blank = excluded.is_blank
                ''', (match_id, end_info['end_number'], end_info.get('team1_score', 0), end_info.get('team2_score', 0), end_info.get('is_blank', 0)))

        conn.commit()
        conn.close()
        return tournament_id

def recalculate_all_medals():
    """
    Computes exact gold, silver, and bronze medal counts for all players across all tournaments.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    print("[Analytics] Recalculating all player medals from tournament standings...")
    cursor.execute("UPDATE players SET gold_medals = 0, silver_medals = 0, bronze_medals = 0")

    cursor.execute('''
    SELECT tt.tournament_id, tt.final_place, tr.player_id, p.full_name
    FROM tournament_teams tt
    JOIN team_rosters tr ON tt.id = tr.tournament_team_id
    JOIN players p ON tr.player_id = p.id
    WHERE tt.final_place IN (1, 2, 3)
    ''')
    rows = cursor.fetchall()
    
    player_medals = {}
    for r in rows:
        pid = r['player_id']
        place = r['final_place']
        if pid not in player_medals:
            player_medals[pid] = {'gold': 0, 'silver': 0, 'bronze': 0}
        if place == 1:
            player_medals[pid]['gold'] += 1
        elif place == 2:
            player_medals[pid]['silver'] += 1
        elif place == 3:
            player_medals[pid]['bronze'] += 1

    for pid, m in player_medals.items():
        cursor.execute('''
        UPDATE players
        SET gold_medals = ?, silver_medals = ?, bronze_medals = ?
        WHERE id = ?
        ''', (m['gold'], m['silver'], m['bronze'], pid))

    conn.commit()
    conn.close()
    print(f"[Analytics] Updated medals for {len(player_medals)} medalists.")
