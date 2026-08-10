import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')
import json
import time
from concurrent.futures import ThreadPoolExecutor

from db.database import init_db, get_db_connection
from scraper.crawler import load_cached_discovery
from scraper.runner import fetch_url_content
from scraper.extractor import parse_tournament_html, clean_text
from scraper.storage import save_tournament_data
from analytics.stats import run_full_analytics
from db.export_to_postgres import export_sqlite_to_postgres_sql

def reprocess_all_tournaments():
    print("=== Starting Full Local Reprocessing with Canonical Names & Strict Disciplines ===")
    
    # 1. Reset database tables
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS player_ratings_history")
    c.execute("DROP TABLE IF EXISTS match_ends")
    c.execute("DROP TABLE IF EXISTS matches")
    c.execute("DROP TABLE IF EXISTS team_rosters")
    c.execute("DROP TABLE IF EXISTS tournament_teams")
    c.execute("DROP TABLE IF EXISTS players")
    c.execute("DROP TABLE IF EXISTS teams")
    c.execute("DROP TABLE IF EXISTS tournaments")
    conn.commit()
    conn.close()

    init_db()

    tournaments_dict = load_cached_discovery()
    print(f"Loaded {len(tournaments_dict)} tournaments from discovered_tournaments.json")

    start_time = time.time()
    success_count = 0
    total_matches = 0
    total_rosters = 0
    total_standings = 0

    for idx, (url, t_info) in enumerate(tournaments_dict.items(), 1):
        base_title = clean_text(t_info.get('title', ''))
        base_date = clean_text(t_info.get('date_display', ''))
        season = t_info.get('season')

        html = fetch_url_content(url)
        if not html:
            continue

        parsed = parse_tournament_html(html, url, base_title=base_title, base_date=base_date, season=season)
        tourn_id = save_tournament_data(parsed, raw_html="")

        success_count += 1
        total_matches += len(parsed['matches'])
        total_rosters += len(parsed['rosters'])
        total_standings += len(parsed['standings'])

        if idx % 50 == 0 or idx == len(tournaments_dict):
            print(f"[{idx}/{len(tournaments_dict)}] ({parsed['discipline']}) {parsed['title'][:40]} | Matches: {len(parsed['matches'])}, Rosters: {len(parsed['rosters'])}, Standings: {len(parsed['standings'])}")

    elapsed = time.time() - start_time
    print(f"\n=== Extracted {success_count} Tournaments in {elapsed:.1f}s ===")
    print(f"Total Matches: {total_matches}, Rosters: {total_rosters}, Standings: {total_standings}")

    print("\n=== Running Analytics Engine ===")
    run_full_analytics()

    print("\n=== Exporting to PostgreSQL ===")
    export_sqlite_to_postgres_sql()

    print("\n=== All Reprocessing Complete! ===")

if __name__ == '__main__':
    reprocess_all_tournaments()
