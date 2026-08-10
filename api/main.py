import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')
import json
import sqlite3
import requests
from typing import Optional, List
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from db.database import get_db_connection
from analytics.stats import run_full_analytics
from scraper.crawler import HEADERS
from scraper.extractor import parse_tournament_html, clean_text
from scraper.runner import get_cache_path

app = FastAPI(
    title="Curling Analytics & Rankings API",
    description="REST API for Russian Curling Federation (curling.ru) data, dynamic Elo ratings, and end statistics (2016-2026)",
    version="2.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")

@app.get("/api/summary")
def get_summary():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM tournaments")
    total_tourn = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM matches")
    total_matches = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM players")
    total_players = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM teams")
    total_teams = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM match_ends")
    total_ends = c.fetchone()[0]
    c.execute("SELECT DISTINCT season FROM tournaments WHERE season IS NOT NULL ORDER BY season DESC")
    seasons = [r[0] for r in c.fetchall()]
    conn.close()
    return {
        "total_tournaments": total_tourn,
        "total_matches": total_matches,
        "total_players": total_players,
        "total_teams": total_teams,
        "total_ends": total_ends,
        "seasons": seasons
    }

@app.get("/api/inspect_tournament")
def inspect_single_tournament(url: str = Query(..., description="Target tournament URL on curling.ru")):
    """
    Real-time deep inspection endpoint for a single tournament.
    Fetches, extracts, and returns granular data (standings, rosters, matches, ends, PDFs).
    """
    html = ""
    # Try local cache first
    c_path = get_cache_path(url)
    if os.path.exists(c_path):
        try:
            with open(c_path, 'r', encoding='utf-8') as f:
                html = f.read()
        except Exception:
            pass

    # If not in cache or empty, fetch from curling.ru
    if not html:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200 and r.text:
                html = r.text
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch tournament URL: {e}")

    if not html:
        raise HTTPException(status_code=404, detail="Tournament content could not be retrieved")

    parsed = parse_tournament_html(html, url)
    return parsed

@app.get("/api/rankings")
def get_player_rankings(
    discipline: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    season: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("fcf_points"),
    order: str = Query("desc"),
    min_matches: int = Query(1),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    conn = get_db_connection()
    c = conn.cursor()

    if search:
        min_matches = 0

    if discipline:
        # Query discipline-isolated points and stats
        valid_sorts = {
            "fcf_points": "pds.fcf_points",
            "elo_rating": "p.elo_rating",
            "win_rate": "pds.win_rate",
            "matches_played": "pds.matches_played",
            "gold_medals": "pds.gold_medals"
        }
        sort_col = valid_sorts.get(sort_by, "pds.fcf_points")
        sort_dir = "DESC" if order.lower() == "desc" else "ASC"

        where_clauses = ["pds.discipline = ?", "pds.matches_played >= ?"]
        params = [discipline, min_matches]

        if discipline in ['classic_men', 'juniors_m']:
            where_clauses.append("(p.gender = 'M' OR p.gender IS NULL)")
        elif discipline in ['classic_women', 'juniors_w']:
            where_clauses.append("p.gender = 'F'")

        if search:
            where_clauses.append("(p.full_name LIKE ? OR p.normalized_name LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        sql = f'''
        SELECT p.id, p.full_name, p.normalized_name, p.gender,
               pds.fcf_points, p.elo_rating, pds.matches_played, pds.matches_won, pds.matches_lost, pds.win_rate,
               pds.gold_medals, pds.silver_medals, pds.bronze_medals,
               p.ends_played, p.ends_won,
               p.hammer_conversion_rate, p.steal_rate, p.force_rate
        FROM player_discipline_stats pds
        JOIN players p ON pds.player_id = p.id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY {sort_col} {sort_dir}, pds.is_skip DESC, pds.gold_medals DESC, p.elo_rating DESC, pds.matches_played DESC
        LIMIT ? OFFSET ?
        '''
        params.extend([limit, offset])
        c.execute(sql, params)
        rows = c.fetchall()

    else:
        # Overall rankings across all disciplines
        valid_sorts = {
            "fcf_points": "p.fcf_points",
            "elo_rating": "p.elo_rating",
            "win_rate": "p.win_rate",
            "matches_played": "p.matches_played",
            "gold_medals": "p.gold_medals"
        }
        sort_col = valid_sorts.get(sort_by, "p.fcf_points")
        sort_dir = "DESC" if order.lower() == "desc" else "ASC"

        where_clauses = ["p.matches_played >= ?"]
        params = [min_matches]

        if gender:
            where_clauses.append("p.gender = ?")
            params.append(gender)

        if search:
            where_clauses.append("(p.full_name LIKE ? OR p.normalized_name LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        sql = f'''
        SELECT p.id, p.full_name, p.normalized_name, p.gender,
               p.fcf_points, p.elo_rating, p.matches_played, p.matches_won, p.matches_lost, p.win_rate,
               p.gold_medals, p.silver_medals, p.bronze_medals,
               p.ends_played, p.ends_won,
               p.hammer_conversion_rate, p.steal_rate, p.force_rate
        FROM players p
        WHERE {' AND '.join(where_clauses)}
        ORDER BY {sort_col} {sort_dir}, p.elo_rating DESC, p.matches_played DESC
        LIMIT ? OFFSET ?
        '''
        params.extend([limit, offset])
        c.execute(sql, params)
        rows = c.fetchall()

    results = []
    for idx, r in enumerate(rows):
        results.append({
            "rank": offset + idx + 1,
            "id": r['id'],
            "full_name": r['full_name'],
            "gender": r['gender'],
            "fcf_points": r['fcf_points'] or 0.0,
            "elo_rating": r['elo_rating'],
            "matches_played": r['matches_played'],
            "matches_won": r['matches_won'],
            "matches_lost": r['matches_lost'],
            "win_rate": r['win_rate'],
            "gold_medals": r['gold_medals'],
            "silver_medals": r['silver_medals'],
            "bronze_medals": r['bronze_medals'],
            "ends_played": r['ends_played'],
            "ends_won": r['ends_won'],
            "hammer_conversion_rate": r['hammer_conversion_rate'],
            "steal_rate": r['steal_rate'],
            "force_rate": r['force_rate']
        })

    conn.close()
    return results

@app.get("/api/teams")
def get_teams_rankings(
    discipline: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    conn = get_db_connection()
    c = conn.cursor()

    where_clauses = ["1=1"]
    params = []

    if discipline:
        where_clauses.append("t.discipline = ?")
        params.append(discipline)

    if search:
        where_clauses.append("(t.name LIKE ? OR t.clean_name LIKE ? OR t.skip_name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    sql = f'''
    SELECT t.id, t.name, t.clean_name, t.skip_name, t.discipline, t.category, t.fcf_points,
           COUNT(DISTINCT tt.tournament_id) as tournaments_played,
           SUM(CASE WHEN tt.final_place = 1 THEN 1 ELSE 0 END) as golds,
           SUM(CASE WHEN tt.final_place = 2 THEN 1 ELSE 0 END) as silvers,
           SUM(CASE WHEN tt.final_place = 3 THEN 1 ELSE 0 END) as bronzes,
           ROUND(AVG(p.elo_rating), 1) as avg_team_elo,
           (SELECT COUNT(DISTINCT m.id) FROM matches m JOIN tournament_teams tt2 ON tt2.tournament_id = m.tournament_id AND (m.team1_name = tt2.team_display_name OR m.team2_name = tt2.team_display_name) WHERE tt2.team_id = t.id) as matches_played,
           (SELECT COUNT(DISTINCT m.id) FROM matches m JOIN tournament_teams tt2 ON tt2.tournament_id = m.tournament_id AND m.winner_name = tt2.team_display_name WHERE tt2.team_id = t.id) as matches_won
    FROM teams t
    LEFT JOIN tournament_teams tt ON t.id = tt.team_id
    LEFT JOIN team_rosters tr ON tt.id = tr.tournament_team_id
    LEFT JOIN players p ON tr.player_id = p.id
    WHERE {' AND '.join(where_clauses)}
    GROUP BY t.id
    HAVING tournaments_played > 0
    ORDER BY t.fcf_points DESC, golds DESC, silvers DESC, bronzes DESC, avg_team_elo DESC
    LIMIT ? OFFSET ?
    '''
    params.extend([limit, offset])

    c.execute(sql, params)
    rows = c.fetchall()

    results = []
    for idx, r in enumerate(rows):
        played = r['matches_played'] or 0
        won = r['matches_won'] or 0
        lost = max(0, played - won)
        win_rate = round(won / played * 100.0, 1) if played > 0 else 0.0

        results.append({
            "rank": offset + idx + 1,
            "id": r['id'],
            "name": r['clean_name'] or r['name'],
            "skip_name": r['skip_name'] or "",
            "discipline": r['discipline'],
            "category": r['category'],
            "fcf_points": r['fcf_points'] or 0.0,
            "tournaments_played": r['tournaments_played'],
            "matches_played": played,
            "matches_won": won,
            "matches_lost": lost,
            "win_rate": win_rate,
            "gold_medals": r['golds'] or 0,
            "silver_medals": r['silvers'] or 0,
            "bronze_medals": r['bronzes'] or 0,
            "avg_team_elo": r['avg_team_elo'] or 1500.0
        })

    conn.close()
    return results

@app.get("/api/tournaments")
def get_tournaments(
    season: Optional[int] = Query(None),
    discipline: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    conn = get_db_connection()
    c = conn.cursor()

    where_clauses = ["1=1"]
    params = []

    if season:
        where_clauses.append("season = ?")
        params.append(season)

    if discipline:
        where_clauses.append("discipline = ?")
        params.append(discipline)

    if category:
        where_clauses.append("category = ?")
        params.append(category)

    if search:
        where_clauses.append("(title LIKE ? OR location LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    count_sql = f"SELECT COUNT(*) FROM tournaments WHERE {' AND '.join(where_clauses)}"
    c.execute(count_sql, params)
    total_count = c.fetchone()[0]

    sql = f'''
    SELECT t.id, t.url, t.title, t.season, t.date_display, t.discipline, t.category, t.gender_age, t.location, t.pdf_links_json,
           t.tier, t.tier_name, t.base_points,
           (SELECT COUNT(*) FROM matches m WHERE m.tournament_id = t.id) as matches_count,
           (SELECT COUNT(*) FROM tournament_teams tt WHERE tt.tournament_id = t.id) as teams_count,
           (SELECT tt.team_display_name FROM tournament_teams tt WHERE tt.tournament_id = t.id AND (tt.final_place = 1 OR tt.place_text LIKE '%1 место%') LIMIT 1) as winner_name,
           (SELECT tt.skip_name FROM tournament_teams tt WHERE tt.tournament_id = t.id AND (tt.final_place = 1 OR tt.place_text LIKE '%1 место%') LIMIT 1) as winner_skip
    FROM tournaments t
    WHERE {' AND '.join(where_clauses)}
    ORDER BY t.season DESC, t.id ASC
    LIMIT ? OFFSET ?
    '''
    params.extend([limit, offset])

    c.execute(sql, params)
    rows = c.fetchall()

    items = []
    for r in rows:
        pdf_links = json.loads(r['pdf_links_json']) if r['pdf_links_json'] else []
        items.append({
            "id": r['id'],
            "url": r['url'],
            "title": r['title'],
            "season": r['season'],
            "date_display": r['date_display'],
            "discipline": r['discipline'],
            "category": r['category'],
            "gender_age": r['gender_age'],
            "location": r['location'],
            "tier": r['tier'] or "",
            "tier_name": r['tier_name'] or "Всероссийские соревнования",
            "base_points": r['base_points'] or 250,
            "matches_count": r['matches_count'] or 0,
            "teams_count": r['teams_count'] or 0,
            "winner_name": r['winner_name'] or "",
            "winner_skip": r['winner_skip'] or "",
            "pdf_links": pdf_links
        })

    conn.close()
    return items

@app.get("/api/tournaments/{tournament_id}")
def get_tournament_details(tournament_id: int):
    conn = get_db_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM tournaments WHERE id = ?", (tournament_id,))
    t_row = c.fetchone()
    if not t_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Tournament not found")

    pdf_links = json.loads(t_row['pdf_links_json']) if t_row['pdf_links_json'] else []

    c.execute('''
    SELECT tt.id, tt.team_display_name, tt.skip_name, tt.final_place, tt.place_text, tt.coach,
           t.clean_name
    FROM tournament_teams tt
    LEFT JOIN teams t ON tt.team_id = t.id
    WHERE tt.tournament_id = ?
    ORDER BY CASE WHEN tt.final_place IS NOT NULL AND tt.final_place > 0 THEN tt.final_place ELSE 999 END ASC, tt.id ASC
    ''', (tournament_id,))
    standings_rows = c.fetchall()

    standings = []
    for sr in standings_rows:
        tt_id = sr['id']
        c.execute('''
        SELECT p.full_name, tr.role
        FROM team_rosters tr
        JOIN players p ON tr.player_id = p.id
        WHERE tr.tournament_team_id = ?
        ORDER BY tr.order_index ASC
        ''', (tt_id,))
        p_rows = c.fetchall()
        p_names = [pr['full_name'] for pr in p_rows]

        standings.append({
            "place": sr['final_place'],
            "final_place": sr['final_place'],
            "place_text": sr['place_text'] or str(sr['final_place'] or ""),
            "team_name": sr['team_display_name'],
            "team_display_name": sr['team_display_name'],
            "clean_name": sr['clean_name'] or sr['team_display_name'],
            "skip_name": sr['skip_name'] or "",
            "coach": sr['coach'] or "",
            "roster_players": p_names
        })

    c.execute('''
    SELECT tt.id as tt_id, tt.team_display_name, tt.skip_name, tt.coach,
           p.id as player_id, p.full_name, p.gender, p.elo_rating, p.fcf_points, tr.role, tr.order_index
    FROM tournament_teams tt
    JOIN team_rosters tr ON tt.id = tr.tournament_team_id
    JOIN players p ON tr.player_id = p.id
    WHERE tt.tournament_id = ?
    ORDER BY tt.id ASC, tr.order_index ASC
    ''', (tournament_id,))
    roster_rows = c.fetchall()

    rosters_dict = {}
    for rr in roster_rows:
        tt_id = rr['tt_id']
        if tt_id not in rosters_dict:
            rosters_dict[tt_id] = {
                "team_name": rr['team_display_name'],
                "skip": rr['skip_name'] or "",
                "coach": rr['coach'] or "",
                "players": []
            }
        rosters_dict[tt_id]["players"].append({
            "player_id": rr['player_id'],
            "name": rr['full_name'],
            "role": rr['role'],
            "gender": rr['gender'],
            "elo_rating": rr['elo_rating'],
            "fcf_points": rr['fcf_points'] or 0.0
        })

    c.execute('''
    SELECT m.*, me.end_number, me.team1_score, me.team2_score, me.is_blank
    FROM matches m
    LEFT JOIN match_ends me ON m.id = me.match_id
    WHERE m.tournament_id = ?
    ORDER BY m.id ASC, me.end_number ASC
    ''', (tournament_id,))
    match_rows = c.fetchall()

    matches_dict = {}
    for mr in match_rows:
        m_id = mr['id']
        if m_id not in matches_dict:
            matches_dict[m_id] = {
                "id": m_id,
                "tour_name": mr['tour_name'],
                "stage_type": mr['stage_type'],
                "match_identifier": mr['match_identifier'],
                "team1_name": mr['team1_name'],
                "team2_name": mr['team2_name'],
                "team1_skip": mr['team1_skip'],
                "team2_skip": mr['team2_skip'],
                "team1_hammer_start": mr['team1_hammer_start'],
                "team2_hammer_start": mr['team2_hammer_start'],
                "team1_total_score": mr['team1_total_score'],
                "team2_total_score": mr['team2_total_score'],
                "winner_name": mr['winner_name'],
                "ends": []
            }
        if mr['end_number'] is not None:
            matches_dict[m_id]["ends"].append({
                "end_number": mr['end_number'],
                "team1_score": mr['team1_score'],
                "team2_score": mr['team2_score'],
                "is_blank": mr['is_blank']
            })

    tours_dict = {}
    for m in matches_dict.values():
        tour = m['tour_name'] or "Матчи"
        tours_dict.setdefault(tour, []).append(m)

    tours = [{"tour_name": k, "matches": v} for k, v in tours_dict.items()]

    conn.close()
    return {
        "id": t_row['id'],
        "url": t_row['url'],
        "title": t_row['title'],
        "season": t_row['season'],
        "date_display": t_row['date_display'],
        "discipline": t_row['discipline'],
        "category": t_row['category'],
        "gender_age": t_row['gender_age'],
        "location": t_row['location'],
        "tier": t_row['tier'] or "",
        "tier_name": t_row['tier_name'] or "Всероссийские соревнования",
        "base_points": t_row['base_points'] or 200,
        "pdf_links": pdf_links,
        "standings": standings,
        "rosters": list(rosters_dict.values()),
        "matches": list(matches_dict.values()),
        "tours": tours
    }

@app.get("/api/players/{player_id}")
def get_player_profile(player_id: int):
    conn = get_db_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM players WHERE id = ?", (player_id,))
    p_row = c.fetchone()
    if not p_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Player not found")

    c.execute('''
    SELECT t.id, t.title, t.season, t.date_display, t.discipline, t.category,
           t.tier, t.tier_name, t.base_points,
           tt.team_display_name, tt.skip_name, tt.final_place, tt.place_text, tr.role
    FROM team_rosters tr
    JOIN tournament_teams tt ON tr.tournament_team_id = tt.id
    JOIN tournaments t ON tt.tournament_id = t.id
    WHERE tr.player_id = ?
    ORDER BY t.season DESC, t.id DESC
    ''', (player_id,))
    tourn_rows = c.fetchall()

    tournaments = []
    for tr in tourn_rows:
        tournaments.append({
            "tournament_id": tr['id'],
            "title": tr['title'],
            "season": tr['season'],
            "date_display": tr['date_display'],
            "discipline": tr['discipline'],
            "category": tr['category'],
            "tier_name": tr['tier_name'] or "Всероссийские соревнования",
            "base_points": tr['base_points'] or 250,
            "team_name": tr['team_display_name'],
            "skip_name": tr['skip_name'],
            "role": tr['role'],
            "final_place": tr['final_place'],
            "place_text": tr['place_text']
        })

    c.execute('''
    SELECT date, old_rating, new_rating, rating_change
    FROM player_ratings_history
    WHERE player_id = ?
    ORDER BY id ASC
    ''', (player_id,))
    history_rows = c.fetchall()
    history = [{"date": r['date'], "rating": r['new_rating'], "change": r['rating_change']} for r in history_rows]

    c.execute('''
    SELECT discipline, fcf_points, matches_played, matches_won, matches_lost, win_rate,
           gold_medals, silver_medals, bronze_medals
    FROM player_discipline_stats
    WHERE player_id = ?
    ORDER BY fcf_points DESC
    ''', (player_id,))
    disc_rows = c.fetchall()
    discipline_breakdown = []
    for dr in disc_rows:
        discipline_breakdown.append({
            "discipline": dr['discipline'],
            "fcf_points": dr['fcf_points'] or 0.0,
            "matches_played": dr['matches_played'],
            "matches_won": dr['matches_won'],
            "matches_lost": dr['matches_lost'],
            "win_rate": dr['win_rate'],
            "gold_medals": dr['gold_medals'],
            "silver_medals": dr['silver_medals'],
            "bronze_medals": dr['bronze_medals']
        })

    conn.close()
    return {
        "id": p_row['id'],
        "full_name": p_row['full_name'],
        "gender": p_row['gender'],
        "fcf_points": p_row['fcf_points'] or 0.0,
        "elo_rating": p_row['elo_rating'],
        "matches_played": p_row['matches_played'],
        "matches_won": p_row['matches_won'],
        "matches_lost": p_row['matches_lost'],
        "win_rate": p_row['win_rate'],
        "gold_medals": p_row['gold_medals'],
        "silver_medals": p_row['silver_medals'],
        "bronze_medals": p_row['bronze_medals'],
        "ends_played": p_row['ends_played'],
        "ends_won": p_row['ends_won'],
        "hammer_conversion_rate": p_row['hammer_conversion_rate'],
        "steal_rate": p_row['steal_rate'],
        "force_rate": p_row['force_rate'],
        "discipline_breakdown": discipline_breakdown,
        "tournaments": tournaments,
        "rating_history": history
    }

@app.post("/api/recalculate_analytics")
def recalculate_analytics():
    run_full_analytics()
    return {"status": "success", "message": "Analytics recalculated successfully"}

if os.path.exists(WEB_DIR):
    app.mount("/css", StaticFiles(directory=os.path.join(WEB_DIR, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(WEB_DIR, "js")), name="js")

    @app.get("/")
    def serve_frontend():
        return FileResponse(os.path.join(WEB_DIR, "index.html"))
