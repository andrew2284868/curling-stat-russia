import re
import requests
from bs4 import BeautifulSoup
import time
import json
import os
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest"
}

CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "discovered_tournaments.json")

def load_cached_discovery() -> Dict[str, Dict]:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_cached_discovery(tourn_dict: Dict[str, Dict]):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(tourn_dict, f, ensure_ascii=False, indent=2)

def discover_archive_tournaments() -> List[Dict]:
    url = "https://curling.ru/arhiv-sorevnovaniy/"
    print(f"[Crawler] Fetching archive from {url}...", flush=True)
    tournaments = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'lxml')
            items = soup.select('.archive_item')
            for it in items:
                href = it.get('href')
                if not href:
                    continue
                if not href.startswith('http'):
                    href = f"https://curling.ru{href}" if href.startswith('/') else f"https://curling.ru/{href}"
                
                time_el = it.select_one('.news_item_time')
                title_el = it.select_one('.news_item_title')
                date_str = time_el.text.strip() if time_el else ""
                title_str = title_el.text.strip() if title_el else ""
                
                season = None
                if date_str and '.' in date_str:
                    try:
                        season = int(date_str.split('.')[-1])
                    except ValueError:
                        pass
                if not season:
                    m = re.search(r'20\d{2}', title_str)
                    if m:
                        season = int(m.group(0))

                tournaments.append({
                    "url": href,
                    "title": title_str,
                    "date_display": date_str,
                    "season": season,
                    "source_type": "archive"
                })
    except Exception as e:
        print(f"[Crawler] Error fetching archive: {e}", flush=True)
    
    print(f"[Crawler] Discovered {len(tournaments)} tournaments in archive.", flush=True)
    return tournaments

def fetch_single_calendar_event(item_tuple):
    start, end, name, time_val = item_tuple
    events = []
    try:
        ajax_res = requests.post(
            "https://curling.ru/extore/frontend/themes/kerling/calendar_ajax.php",
            data={"date": time_val},
            headers=HEADERS,
            timeout=10
        )
        if ajax_res.status_code == 200 and ajax_res.text:
            ajax_soup = BeautifulSoup(ajax_res.text, 'lxml')
            for a_it in ajax_soup.select('.ivent_item'):
                a_link = a_it.select_one('.ivent_title')
                if a_link and a_link.get('href'):
                    href = a_link['href']
                    if not href.startswith('http'):
                        href = f"https://curling.ru{href}" if href.startswith('/') else f"https://curling.ru/{href}"
                    date_span = a_it.select_one('.ivent_date')
                    d_text = date_span.text.strip() if date_span else f"{start[:10]} - {end[:10]}"
                    y_val = int(start[:4]) if start else 2024
                    events.append({
                        "url": href,
                        "title": a_link.text.strip() or name,
                        "date_display": d_text,
                        "season": y_val,
                        "source_type": "calendar"
                    })
    except Exception:
        pass
    return events

def discover_calendar_tournaments() -> List[Dict]:
    url = "https://curling.ru/kalendar/"
    print(f"[Crawler] Fetching calendar from {url}...", flush=True)
    tournaments = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'lxml')
            
            for it in soup.select('.ivent_item'):
                a = it.select_one('.ivent_title')
                date_el = it.select_one('.ivent_date')
                if a and a.get('href'):
                    href = a['href']
                    if not href.startswith('http'):
                        href = f"https://curling.ru{href}" if href.startswith('/') else f"https://curling.ru/{href}"
                    title = a.text.strip()
                    date_str = date_el.text.strip() if date_el else ""
                    m = re.search(r'20\d{2}', title)
                    season = int(m.group(0)) if m else 2026
                    tournaments.append({
                        "url": href,
                        "title": title,
                        "date_display": date_str,
                        "season": season,
                        "source_type": "calendar"
                    })

            m = re.search(r'eventsData\s*:\s*\[(.*?)\]\s*,\s*dateChanged', r.text, re.DOTALL)
            if m:
                events_raw = m.group(1)
                items = re.findall(r'\{\s*start:\s*"(.*?)",\s*end:\s*"(.*?)",\s*name:\s*"(.*?)",\s*time:\s*"(.*?)"\s*\}', events_raw)
                print(f"[Crawler] Found {len(items)} events in calendar JS array. Fetching URLs with 12 threads...", flush=True)
                
                with ThreadPoolExecutor(max_workers=12) as ex:
                    res_lists = ex.map(fetch_single_calendar_event, items)
                    for r_list in res_lists:
                        tournaments.extend(r_list)

    except Exception as e:
        print(f"[Crawler] Error fetching calendar: {e}", flush=True)

    print(f"[Crawler] Discovered {len(tournaments)} tournaments from calendar.", flush=True)
    return tournaments

def discover_results_tournaments() -> List[Dict]:
    tournaments = []
    for cat_id in ["1678343682", "1678343675"]:
        url = f"https://curling.ru/rezultaty-sorevnovaniy?result={cat_id}"
        print(f"[Crawler] Fetching results list from {url}...", flush=True)
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'lxml')
                for it in soup.select('.sort_items > div, .new_news_item'):
                    onclick = it.get('onclick', '')
                    m = re.search(r"window\.location='(.*?)';", onclick)
                    if m:
                        href = m.group(1)
                        if not href.startswith('http'):
                            href = f"https://curling.ru{href}" if href.startswith('/') else f"https://curling.ru/{href}"
                        
                        season_attr = it.get('data-season')
                        title_el = it.select_one('.new_news_title')
                        date_el = it.select_one('.new_news_date')
                        title = title_el.text.strip() if title_el else ""
                        date_str = date_el.text.strip() if date_el else ""
                        
                        season = int(season_attr) if season_attr and season_attr.isdigit() else None
                        if not season:
                            m_y = re.search(r'20\d{2}', title)
                            season = int(m_y.group(0)) if m_y else 2025

                        tournaments.append({
                            "url": href,
                            "title": title,
                            "date_display": date_str,
                            "season": season,
                            "source_type": "results"
                        })
        except Exception as e:
            print(f"[Crawler] Error fetching results {cat_id}: {e}", flush=True)

    print(f"[Crawler] Discovered {len(tournaments)} tournaments from results page.", flush=True)
    return tournaments

def get_all_tournaments(min_year: int = 2016, max_year: int = 2026) -> List[Dict]:
    combined = load_cached_discovery()
    
    archive = discover_archive_tournaments()
    calendar = discover_calendar_tournaments()
    results = discover_results_tournaments()
    
    for t in archive + calendar + results:
        url = t['url'].rstrip('/') + '/'
        if url not in combined:
            combined[url] = t
        else:
            if not combined[url].get('season') and t.get('season'):
                combined[url]['season'] = t['season']
            if not combined[url].get('date_display') and t.get('date_display'):
                combined[url]['date_display'] = t['date_display']
    
    save_cached_discovery(combined)
    all_tourns = list(combined.values())
    
    filtered = []
    for t in all_tourns:
        s = t.get('season')
        if s is None:
            filtered.append(t)
        elif min_year <= s <= max_year:
            filtered.append(t)
            
    print(f"[Crawler] Total unique tournaments between {min_year} and {max_year}: {len(filtered)}", flush=True)
    return filtered

if __name__ == "__main__":
    tourns = get_all_tournaments(2016, 2026)
    print(f"Sample tournament: {tourns[0] if tourns else 'None'}")
