import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')
import json
import time
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from io import BytesIO

from scraper.crawler import HEADERS
from scraper.extractor import (
    parse_tournament_html, clean_text, canonical_russian_name,
    detect_discipline_and_category, is_valid_person_name
)

def fetch_tournament_data_deep(url: str, max_retries: int = 4) -> dict:
    """
    Fetches raw HTML and all related PDF files for a single tournament,
    then performs granular extraction and validation.
    """
    print(f"\n[Inspector] Fetching tournament from: {url}")
    html = ""
    for attempt in range(max_retries):
        try:
            print(f"  Attempt {attempt + 1}/{max_retries}...")
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200 and r.text:
                html = r.text
                print(f"  Successfully fetched HTML ({len(html)} bytes)")
                break
        except Exception as e:
            print(f"  Request error: {e}")
            time.sleep(1 + attempt)

    if not html:
        # Check local cache as fallback
        import hashlib
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache_html")
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
        cache_file = os.path.join(cache_dir, f"{url_hash}.html")
        if os.path.exists(cache_file):
            print(f"  Loaded HTML from local cache: {cache_file}")
            with open(cache_file, 'r', encoding='utf-8') as f:
                html = f.read()

    if not html:
        return {"error": f"Failed to fetch {url}"}

    parsed = parse_tournament_html(html, url)

    # Detailed inspection report
    report = {
        "url": url,
        "title": parsed['title'],
        "season": parsed['season'],
        "date_display": parsed['date_display'],
        "discipline": parsed['discipline'],
        "category": parsed['category'],
        "gender_age": parsed['gender_age'],
        "stats": {
            "standings_count": len(parsed['standings']),
            "rosters_count": len(parsed['rosters']),
            "matches_count": len(parsed['matches']),
            "pdf_count": len(parsed['pdf_links'])
        },
        "standings": parsed['standings'],
        "rosters": parsed['rosters'],
        "matches": parsed['matches'],
        "pdf_links": parsed['pdf_links']
    }

    # Save to local test output
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(output_dir, "last_inspection.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n=======================================================")
    print(f" TOURNAMENT INSPECTION REPORT")
    print(f"=======================================================")
    print(f"Title: {report['title']}")
    print(f"Season: {report['season']} | Date: {report['date_display']}")
    print(f"Discipline: {report['discipline']} ({report['gender_age']})")
    print(f"Standings: {report['stats']['standings_count']} teams")
    print(f"Rosters: {report['stats']['rosters_count']} teams")
    print(f"Matches: {report['stats']['matches_count']} matches")
    print(f"PDFs: {report['stats']['pdf_count']} files")
    
    if report['standings']:
        print(f"\n--- Standings (Top 5) ---")
        for st in report['standings'][:5]:
            place_lbl = f"🥇 1 место" if st['place'] == 1 else (f"🥈 2 место" if st['place'] == 2 else (f"🥉 3 место" if st['place'] == 3 else f"{st['place']} место"))
            print(f"  {place_lbl}: {st['team_name']} | Skip: {st.get('skip_name', '—')}")

    if report['rosters']:
        print(f"\n--- Rosters (Sample 3 teams) ---")
        for r in report['rosters'][:3]:
            pl_str = ", ".join([f"{p['name']} ({p['role']})" if isinstance(p, dict) else str(p) for p in r.get('players', [])])
            print(f"  Team: {r['team_name']}")
            print(f"    Skip: {r.get('skip', '—')} | Coach: {r.get('coach', '—')}")
            print(f"    Players: {pl_str}")

    if report['matches']:
        print(f"\n--- Matches (Sample 5 matches) ---")
        for m in report['matches'][:5]:
            s1 = m['team1_total_score'] if m['team1_total_score'] is not None else '—'
            s2 = m['team2_total_score'] if m['team2_total_score'] is not None else '—'
            h1 = "🔨 " if m.get('team1_hammer_start') else ""
            h2 = "🔨 " if m.get('team2_hammer_start') else ""
            print(f"  [{m.get('tour_name', 'Матч')}] {h1}{m['team1_name']} vs {h2}{m['team2_name']} -> {s1}:{s2} (Ends: {len(m.get('ends', []))})")

    print(f"\nReport saved to: {output_file}")
    return report

if __name__ == "__main__":
    # Test on Чемпионат России среди мужских команд
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://curling.ru/kalendar/chempionat-rossii-sredi-muzhskih-komand-2023/"
    fetch_tournament_data_deep(target_url)
