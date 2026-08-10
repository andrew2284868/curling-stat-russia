import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')
import hashlib
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

from db.database import init_db, get_db_connection
from scraper.crawler import get_all_tournaments, HEADERS
from scraper.extractor import parse_tournament_html, clean_text
from scraper.storage import save_tournament_data
from analytics.stats import run_full_analytics

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache_html")

def get_cache_path(url: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{url_hash}.html")

def fetch_url_content(url: str, max_retries: int = 3) -> str:
    cache_file = get_cache_path(url)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            pass

    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200 and r.text:
                html = r.text
                with open(cache_file, 'w', encoding='utf-8') as f:
                    f.write(html)
                return html
            elif r.status_code == 404:
                return ""
        except Exception:
            time.sleep(0.5 + attempt * 0.5)

    return ""

def process_single_tournament(tourn_info: Dict) -> Dict:
    url = tourn_info['url']
    base_title = clean_text(tourn_info.get('title', ''))
    base_date = clean_text(tourn_info.get('date_display', ''))
    season = tourn_info.get('season')

    html = fetch_url_content(url)
    if not html:
        return {"url": url, "status": "failed_or_empty", "title": base_title, "matches_count": 0, "rosters_count": 0, "standings_count": 0}

    parsed = parse_tournament_html(html, url, base_title=base_title, base_date=base_date, season=season)
    tourn_id = save_tournament_data(parsed, raw_html="")
    
    return {
        "url": url,
        "status": "success",
        "tourn_id": tourn_id,
        "title": parsed['title'],
        "discipline": parsed['discipline'],
        "standings_count": len(parsed['standings']),
        "rosters_count": len(parsed['rosters']),
        "matches_count": len(parsed['matches'])
    }

def run_scraper(min_year: int = 2016, max_year: int = 2026, max_workers: int = 16):
    print(f"=== Starting Curling.ru Scraper ({min_year} - {max_year}) ===", flush=True)
    init_db()
    
    tournaments = get_all_tournaments(min_year, max_year)
    print(f"=== Processing {len(tournaments)} tournaments with {max_workers} threads ===", flush=True)
    
    start_time = time.time()
    results = []
    success_count = 0
    total_matches = 0
    total_rosters = 0
    total_standings = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_single_tournament, t): t for t in tournaments}
        for idx, future in enumerate(as_completed(futures), 1):
            t_info = futures[future]
            try:
                res = future.result()
                results.append(res)
                if res['status'] == 'success':
                    success_count += 1
                    total_matches += res['matches_count']
                    total_rosters += res['rosters_count']
                    total_standings += res['standings_count']
                if idx % 50 == 0 or idx == len(tournaments):
                    print(f"[{idx}/{len(tournaments)}] Processed: {res.get('title', '')[:35]}... (M:{res.get('matches_count', 0)}, R:{res.get('rosters_count', 0)})", flush=True)
            except Exception as e:
                print(f"[{idx}/{len(tournaments)}] Error processing {t_info['url']}: {e}", flush=True)

    elapsed = time.time() - start_time
    print(f"\n=== Scraping Completed in {elapsed:.1f}s ===", flush=True)
    print(f"Total Tournaments Processed: {success_count}/{len(tournaments)}", flush=True)
    print(f"Total Matches Collected: {total_matches}", flush=True)
    print(f"Total Rosters/Teams: {total_rosters}", flush=True)
    print(f"Total Standings: {total_standings}", flush=True)

    print("\n=== Running Analytics & Rating Engine ===", flush=True)
    run_full_analytics()
    print("=== Pipeline Complete! ===", flush=True)

if __name__ == "__main__":
    run_scraper(2016, 2026, max_workers=16)
