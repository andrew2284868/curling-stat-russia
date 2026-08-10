import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')
import json
import re
import glob
import hashlib
from datetime import datetime
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

from scraper.extractor import (
    clean_text, detect_discipline_and_category, parse_tournament_html,
    canonical_russian_name, is_valid_person_name, is_foreign_team
)
from scraper.storage import save_tournament_data
from db.database import init_db, get_db_connection
from analytics.stats import run_full_analytics
from db.export_to_postgres import export_sqlite_to_postgres_sql

CACHE_DIR = r"D:\dev\parser\data\cache_html"

MONTH_MAP = {
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
    'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
    'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4, 'май': 5, 'июнь': 6,
    'июль': 7, 'август': 8, 'сентябрь': 9, 'октябрь': 10, 'ноябрь': 11, 'декабрь': 12
}

def extract_dates_and_title(html: str):
    soup = BeautifulSoup(html, 'lxml')
    h1 = soup.find('h1')
    title = h1.text.strip() if h1 else ""
    if not title and soup.title:
        title = soup.title.text.split('|')[0].strip()
        
    text = soup.get_text(" ", strip=True)
    date_matches = []
    
    p1 = re.findall(r'с\s+(\d{1,2})\s+([а-я]+)(?:\s+(\d{4}))?\s+по\s+(\d{1,2})\s+([а-я]+)\s+(\d{4})', text, re.I)
    for d1, m1_s, y1_s, d2, m2_s, y2_s in p1:
        m1 = MONTH_MAP.get(m1_s.lower())
        m2 = MONTH_MAP.get(m2_s.lower())
        if m1 and m2:
            y2 = int(y2_s)
            y1 = int(y1_s) if y1_s else (y2 if m1 <= m2 else y2 - 1)
            try:
                date_matches.append((datetime(y1, m1, int(d1)), datetime(y2, m2, int(d2))))
            except:
                pass

    p2 = re.findall(r'с\s+(\d{1,2})\s+по\s+(\d{1,2})\s+([а-я]+)\s+(\d{4})', text, re.I)
    for d1, d2, m_s, y_s in p2:
        m = MONTH_MAP.get(m_s.lower())
        if m:
            y = int(y_s)
            try:
                date_matches.append((datetime(y, m, int(d1)), datetime(y, m, int(d2))))
            except:
                pass

    p3 = re.findall(r'(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+([а-я]+)\s+(\d{4})', text, re.I)
    for d1, d2, m_s, y_s in p3:
        m = MONTH_MAP.get(m_s.lower())
        if m:
            y = int(y_s)
            try:
                date_matches.append((datetime(y, m, int(d1)), datetime(y, m, int(d2))))
            except:
                pass

    p4 = re.findall(r'(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+([а-я]+)(?:\s+года)?\s+(\d{4})', text, re.I)
    for d1, d2, m_s, y_s in p4:
        m = MONTH_MAP.get(m_s.lower())
        if m:
            y = int(y_s)
            try:
                date_matches.append((datetime(y, m, int(d1)), datetime(y, m, int(d2))))
            except:
                pass

    best_date = date_matches[0] if date_matches else (None, None)
    return title, best_date, soup

def is_strictly_season_2025_2026(title: str, dt_start, dt_end, html: str, url: str = "", disc_meta: dict = None) -> bool:
    t_low = title.lower()
    
    # 1. Reject if title explicitly contains older years (2016-2024)
    old_year_match = re.search(r'\b(201[6-9]|202[0-4])\b', title)
    if old_year_match and '2025' not in title and '2026' not in title:
        return False
        
    # 2. Reject non-tournament exhibitions
    if 'неделя кёрлинга' in t_low or 'мастер-класс' in t_low or 'фестиваль' in t_low:
        return False
        
    season_start = datetime(2025, 8, 1)
    season_end = datetime(2026, 7, 1)
    
    # 3. Check parsed date bounds
    if dt_start and dt_end:
        if (dt_start >= season_start and dt_start <= season_end) or (dt_end >= season_start and dt_end <= season_end):
            return True
        else:
            return False
            
    # 4. Check calendar date from discovered metadata
    if disc_meta and disc_meta.get('date_display'):
        d_text = disc_meta['date_display']
        # If explicitly marked as 2025 spring/summer (before Aug 2025), reject
        if '2025' in title and any(m in d_text.lower() for m in ['январ', 'феврал', 'март', 'апрел', 'ма', 'июн', 'июл']):
            return False
        elif any(m in d_text.lower() for m in ['январ', 'феврал', 'март', 'апрел', 'ма', 'июн', 'июл']):
            # 2026 spring dates (Championships 2026)
            return True
        elif any(m in d_text.lower() for m in ['август', 'сентябр', 'октябр', 'ноябр', 'декабр']):
            # 2025 autumn dates
            return True
            
    # 5. Reject if title explicitly has "2025" and page text contains spring dates without autumn
    if '2025' in title and not ('2026' in title or '2026' in url):
        # Check if it's autumn 2025
        has_autumn = any(m in t_low or m in html.lower() for m in ['август', 'сентябр', 'октябр', 'ноябр', 'декабр'])
        has_spring = any(m in t_low or m in html.lower() for m in ['январ', 'феврал', 'март', 'апрел', 'ма', 'июн'])
        if has_spring and not has_autumn:
            return False
        if not has_autumn and not ('кубок' in t_low or 'суперлига' in t_low or 'первенство' in t_low or 'отбор' in t_low):
            return False

    # 6. Fallback checks for 2026
    if '2026' in title or '2026' in url:
        return True
    if 'чемпионат россии' in t_low and not old_year_match and not ('2025' in title and not has_autumn):
        return True
    if 'первенство россии' in t_low and not old_year_match and not ('2025' in title and not has_autumn):
        return True
        
    return False

def main():
    print("================================================================")
    print(" 🥌 BUILDING STRICT SEASON 2025/2026 DATASET (Aug 1, 2025 - Jul 1, 2026)")
    print("================================================================")
    
    DISC_PATH = r"D:\dev\parser\data\discovered_tournaments.json"
    disc_map = {}
    if os.path.exists(DISC_PATH):
        try:
            with open(DISC_PATH, "r", encoding="utf-8") as f:
                disc_data = json.load(f)
                disc_map = {v.get('url'): v for v in disc_data.values() if v.get('url')}
        except Exception:
            pass

    files = glob.glob(os.path.join(CACHE_DIR, "*.html"))
    season_items = []
    
    for fpath in files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                html = f.read()
            title, (dt_start, dt_end), soup = extract_dates_and_title(html)
            
            canonical = soup.find('link', rel='canonical')
            url = canonical['href'] if canonical and canonical.get('href') else os.path.basename(fpath)
            
            disc_meta = disc_map.get(url)
            
            if is_strictly_season_2025_2026(title, dt_start, dt_end, html, url=url, disc_meta=disc_meta):
                season_items.append({
                    "html": html,
                    "url": url,
                    "title": title,
                    "dt_start": dt_start,
                    "dt_end": dt_end
                })
        except Exception:
            pass
            
    print(f"Discovered {len(season_items)} candidate tournaments strictly within Season 2025/2026.")
    
    # Initialize fresh SQLite DB strictly for Season 2025/2026
    db_file = r"D:\dev\parser\curling_data.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
            print(f"Removed previous database file: {db_file}")
        except Exception as e:
            print(f"Notice when resetting DB: {e}")
            
    init_db()
    
    def process_item(item):
        try:
            date_str = ""
            if item["dt_start"] and item["dt_end"]:
                date_str = f"{item['dt_start'].strftime('%d.%m.%Y')} – {item['dt_end'].strftime('%d.%m.%Y')}"
            res = parse_tournament_html(
                html=item["html"],
                url=item["url"],
                base_title=item["title"],
                base_date=date_str,
                season=2026
            )
            return res, item["html"]
        except Exception as e:
            print(f"Error parsing {item['url']}: {e}")
            return None, ""

    print(f"Parsing tournaments with verified rosters, skips, and matches...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(process_item, season_items))
        
    valid_results = [r for r in results if r[0] and (r[0].get('matches') or r[0].get('rosters'))]
    
    # Save to SQLite
    total_matches = 0
    total_rosters = 0
    total_standings = 0
    
    for r, raw_html in valid_results:
        t_id = save_tournament_data(r, raw_html)
        total_matches += len(r.get("matches", []))
        total_rosters += len(r.get("rosters", []))
        total_standings += len(r.get("standings", []))

    print(f"\n=== Database Population Complete for Season 2025/2026 ===")
    print(f"Total Official Tournaments in Season: {len(valid_results)}")
    print(f"Total Matches Played: {total_matches}")
    print(f"Total Team Rosters: {total_rosters}")
    print(f"Total Standings: {total_standings}")

    # Breakdown by discipline
    disc_map = {}
    for r, _ in valid_results:
        d = r['discipline']
        disc_map[d] = disc_map.get(d, 0) + 1
        
    print("\n=== Discipline Breakdown (Season 2025/2026) ===")
    for d, c in sorted(disc_map.items(), key=lambda x: x[1], reverse=True):
        print(f"  {d}: {c} tournaments")

    # Run Analytics Engine
    print("\n=== Running Analytics Engine for Season 2025/2026 ===")
    run_full_analytics()
    
    # Export to PostgreSQL
    print("\n=== Exporting to PostgreSQL ===")
    export_sqlite_to_postgres_sql()
    
    print("\n=== Strict Season 2025/2026 Dataset Successfully Built! ===")

if __name__ == "__main__":
    main()
