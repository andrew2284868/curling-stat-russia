import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')
import json
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

from db.database import init_db, get_db_connection
from scraper.crawler import load_cached_discovery
from scraper.extractor import parse_tournament_html, clean_text
from scraper.storage import save_tournament_data
from analytics.stats import run_full_analytics
from db.export_to_postgres import export_sqlite_to_postgres_sql

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache_html")

def get_cache_path(url: str) -> str:
    url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{url_hash}.html")

def process_one(item_tuple):
    url, t_info = item_tuple
    base_title = clean_text(t_info.get('title', ''))
    base_date = clean_text(t_info.get('date_display', ''))
    season = t_info.get('season')

    c_path = get_cache_path(url)
    if not os.path.exists(c_path):
        return None

    try:
        with open(c_path, 'r', encoding='utf-8') as f:
            html = f.read()
    except Exception:
        return None

    if not html:
        return None

    parsed = parse_tournament_html(html, url, base_title=base_title, base_date=base_date, season=season)
    save_tournament_data(parsed, raw_html="")
    return {
        "title": parsed['title'],
        "discipline": parsed['discipline'],
        "matches": len(parsed['matches']),
        "rosters": len(parsed['rosters']),
        "standings": len(parsed['standings'])
    }

def run_fast_reprocess():
    print("=== Starting Fast Multi-threaded Local Reprocessing ===", flush=True)
    
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
    items = list(tournaments_dict.items())
    print(f"Loaded {len(items)} tournaments. Processing with 16 threads...", flush=True)

    start_time = time.time()
    processed_count = 0
    total_matches = 0
    total_rosters = 0
    total_standings = 0

    with ThreadPoolExecutor(max_workers=16) as ex:
        futures = {ex.submit(process_one, item): item for item in items}
        for idx, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            if res:
                processed_count += 1
                total_matches += res['matches']
                total_rosters += res['rosters']
                total_standings += res['standings']
            if idx % 100 == 0 or idx == len(items):
                print(f"[{idx}/{len(items)}] Processed. Total matches so far: {total_matches}", flush=True)

    elapsed = time.time() - start_time
    print(f"\n=== Extracted {processed_count} Tournaments in {elapsed:.1f}s ===", flush=True)
    print(f"Total Matches: {total_matches}, Rosters: {total_rosters}, Standings: {total_standings}", flush=True)

    print("\n=== Running Analytics Engine ===", flush=True)
    run_full_analytics()

    print("\n=== Exporting to PostgreSQL ===", flush=True)
    export_sqlite_to_postgres_sql()

    print("\n=== All Reprocessing Complete! ===", flush=True)

if __name__ == '__main__':
    run_fast_reprocess()
