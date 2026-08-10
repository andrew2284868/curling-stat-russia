import re
from bs4 import BeautifulSoup
import unicodedata
from typing import List, Dict, Tuple, Optional

# Master Russian Name Dictionaries
MALE_FIRST_NAMES = {
    'алексей', 'александр', 'сергей', 'дмитрий', 'даниил', 'данил', 'артур', 'евгений', 'михаил',
    'роман', 'антон', 'петр', 'пётр', 'вадим', 'кирилл', 'никита', 'иван', 'василий',
    'георгий', 'тимур', 'илья', 'герман', 'олег', 'андрей', 'артем', 'артём', 'владимир',
    'виктор', 'николай', 'владислав', 'константин', 'павел', 'вячеслав', 'ярослав', 'тимофей',
    'глеб', 'матвей', 'денис', 'максим', 'эмиль', 'аркадий', 'пантелеймон', 'семен', 'семён',
    'егор', 'лев', 'данила', 'степан', 'федор', 'фёдор', 'борис', 'игорь', 'юрий', 'юра',
    'влад', 'станислав', 'григорий', 'валентин', 'всеволод', 'филипп', 'анатолий', 'ян', 'захар', 'арсений'
}

FEMALE_FIRST_NAMES = {
    'алина', 'анна', 'кира', 'диана', 'виктория', 'галина', 'дарья', 'екатерина', 'елизавета',
    'юлиана', 'наталия', 'наталья', 'мария', 'полина', 'ульяна', 'анастасия', 'владислава',
    'валерия', 'евгения', 'арина', 'софья', 'софия', 'вера', 'ольга', 'маргарита', 'ксения',
    'людмила', 'ирина', 'надежда', 'елена', 'татьяна', 'юлия', 'светлана', 'александра',
    'варвара', 'алиса', 'ярослава', 'мила', 'кристина', 'вероника', 'кссения', 'лариса', 'алла'
}

ALL_FIRST_NAMES = MALE_FIRST_NAMES | FEMALE_FIRST_NAMES

NON_PERSON_WORDS = {
    'г.', 'г', 'санкт-петербург', 'москва', 'краснодарский', 'край', 'московская', 'область',
    'челябинск', 'новосибирск', 'иркутск', 'красноярск', 'ярославль', 'самара', 'сборная',
    'россия', 'russia', 'швсм', 'уор', 'сшор', 'москвич', 'адамант', 'воробьевы', 'горы',
    'динамо', 'тисби', 'ленинградская', 'татарстан', 'башкортостан', 'удмуртия', 'калининград',
    'свердловск', 'кузбасс', 'красноярский', 'новосибирская', 'иркутская', 'челябинская',
    'калининградская', 'кемеровская', 'самарская', 'ярославская', 'уор№2', 'уор-2', 'комсомолл'
}

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize('NFC', str(text))
    text = text.replace('\xa0', ' ').replace('\u200b', '').strip()
    return re.sub(r'\s+', ' ', text)

def fix_russian_spelling(word: str) -> str:
    w = word.strip()
    w_low = w.lower()
    corrections = {
        'сергеи': 'Сергей', 'алексеи': 'Алексей', 'николаи': 'Николай', 'дмитрии': 'Дмитрий',
        'андреи': 'Андрей', 'тимофеи': 'Тимофей', 'матвеи': 'Матвей', 'евгении': 'Евгений',
        'аркадии': 'Аркадий', 'василии': 'Василий', 'юрии': 'Юрий', 'григории': 'Григорий',
        'валерии': 'Валерий', 'анатолии': 'Анатолий', 'виталии': 'Виталий', 'геннадии': 'Геннадий'
    }
    if w_low in corrections:
        return corrections[w_low]
    return w

def canonical_russian_name(raw_name: str) -> str:
    if not raw_name:
        return ""
    
    name = clean_text(raw_name)
    name = re.sub(r'^(?:№\s*\d+|\d{1,2}[\s.\-–—:]+|[A-Fa-fА-Яа-я][.:])\s*', '', name)
    name = re.sub(r'\s*\([Сс]кип.*?\)', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\([Вв][.-]?[Сс]кип.*?\)', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\([Зз]ап.*?\)', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\([Тт]ренер.*?\)', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\(.*?\)', '', name)
    name = re.sub(r'[^\w\s-]', '', name).strip()
    
    raw_words = name.split()
    if not raw_words:
        return ""
    
    words = []
    for w in raw_words:
        if not w:
            continue
        if '-' in w:
            parts = [fix_russian_spelling(p).capitalize() for p in w.split('-') if p]
            words.append('-'.join(parts))
        else:
            words.append(fix_russian_spelling(w).capitalize())
    
    if len(words) == 1:
        return words[0]
        
    elif len(words) == 2:
        w0_low = words[0].lower().replace('ё', 'е')
        w1_low = words[1].lower().replace('ё', 'е')
        
        if w0_low in ALL_FIRST_NAMES and w1_low not in ALL_FIRST_NAMES:
            return f"{words[1]} {words[0]}"
        elif w1_low in ALL_FIRST_NAMES and w0_low not in ALL_FIRST_NAMES:
            return f"{words[0]} {words[1]}"
        elif any(w0_low.endswith(s) for s in ['ов', 'ев', 'ин', 'ын', 'ский', 'цкий', 'ова', 'ева', 'ина', 'ская', 'цкая']):
            return f"{words[0]} {words[1]}"
        elif any(w1_low.endswith(s) for s in ['ов', 'ев', 'ин', 'ын', 'ский', 'цкий', 'ова', 'ева', 'ина', 'ская', 'цкая']):
            return f"{words[1]} {words[0]}"
        else:
            return f"{words[0]} {words[1]}"
            
    elif len(words) == 3:
        w0_low = words[0].lower().replace('ё', 'е')
        w1_low = words[1].lower().replace('ё', 'е')
        w2_low = words[2].lower().replace('ё', 'е')
        
        if w2_low.endswith(('вич', 'вна')):
            if w0_low in ALL_FIRST_NAMES:
                return f"{words[2]} {words[0]}"
            else:
                return f"{words[0]} {words[1]}"
        elif w1_low.endswith(('вич', 'вна')):
            return f"{words[2]} {words[0]}"
        else:
            if w0_low in ALL_FIRST_NAMES:
                return f"{words[1]} {words[0]}"
            return f"{words[0]} {words[1]}"
            
    elif len(words) >= 4:
        return f"{words[0]} {words[1]}"
        
    return " ".join(words)

def is_valid_person_name(name: str) -> bool:
    if not name or len(name) < 3:
        return False
    words = [w.lower() for w in name.split()]
    for w in words:
        if w in NON_PERSON_WORDS:
            return False
    return True

def clean_team_name_for_display(name: str) -> str:
    if not name:
        return ""
    t = clean_text(name)
    t = re.sub(r'^[^\w]+', '', t)
    t = re.sub(r'\s*\((.*?)\)', '', t)
    regions = [
        'Санкт-Петербург', 'Москва', 'Краснодарский край', 'Московская область',
        'Новосибирская область', 'Челябинская область', 'Иркутская область', 'Самарская область',
        'Ярославская область', 'Свердловская область', 'Калининградская область',
        'Красноярский край', 'Кузбасс', 'Кемеровская область', 'Удмуртская Республика',
        'Татарстан', 'Башкортостан'
    ]
    for r in regions:
        pattern = re.compile(re.escape(r) + r'\s*' + re.escape(r), re.IGNORECASE)
        t = pattern.sub(r, t)
    
    t = re.sub(r'[гГ]\.?\s*$', '', t).strip()
    return clean_text(t)

def detect_discipline_and_category(title: str) -> Tuple[str, str, str]:
    t = clean_text(title).lower()
    
    is_wheelchair = 'пода' in t or 'коляск' in t or 'wheelchair' in t
    
    is_u22 = 'до 22' in t or 'u22' in t or 'u-22' in t
    is_u19 = 'до 19' in t or 'u19' in t or 'u-19' in t
    is_u17 = 'до 17' in t or 'u17' in t or 'u-17' in t
    is_youth = is_u22 or is_u19 or is_u17 or 'юниор' in t or 'юнош' in t or 'девуш' in t or 'первенство' in t or 'спартакиад' in t or 'дети азии' in t
    
    is_md = ('смешанн' in t and ('пар' in t or 'дабл' in t)) or 'mixed doubles' in t or 'см. пар' in t or 'см.пар' in t or 'мд' in t
    is_mixed = ('микст' in t or 'смешанн' in t or 'mixed' in t) and not is_md
    
    is_seniors = 'сеньор' in t or 'ветераны' in t or 'ветеран' in t or 'senior' in t or 'seniors' in t
    is_students = 'студент' in t or 'слк' in t or 'вуз' in t or 'универсиад' in t or 'student' in t
    
    is_women = 'женщин' in t or 'женск' in t or 'девушек' in t or 'девушк' in t or 'юниорок' in t or 'women' in t or 'female' in t or 'ladies' in t
    is_men = ('мужчин' in t or 'мужск' in t or 'юношей' in t or 'юнош' in t or 'юниоров' in t or 'men' in t or 'male' in t) and not is_women

    if is_wheelchair:
        if is_md:
            discipline = 'wheelchair_mixed_doubles'
            gender_age = 'wheelchair_md'
        else:
            discipline = 'wheelchair'
            gender_age = 'wheelchair'
    elif is_seniors:
        discipline = 'seniors'
        gender_age = 'seniors_m' if is_men else ('seniors_w' if is_women else 'seniors')
    elif is_students:
        discipline = 'students'
        gender_age = 'students_m' if is_men else ('students_w' if is_women else 'students')
    elif is_youth:
        if is_md or is_mixed:
            discipline = 'juniors_mixed'
            gender_age = 'juniors_mixed'
        elif is_women:
            discipline = 'juniors_w'
            gender_age = 'juniors_w'
        elif is_men:
            discipline = 'juniors_m'
            gender_age = 'juniors_m'
        else:
            discipline = 'juniors_m'
            gender_age = 'juniors'
    elif is_md:
        discipline = 'mixed_doubles'
        gender_age = 'mixed_doubles'
    elif is_mixed:
        discipline = 'mixed'
        gender_age = 'mixed'
    elif is_women:
        discipline = 'classic_women'
        gender_age = 'women'
    elif is_men:
        discipline = 'classic_men'
        gender_age = 'men'
    else:
        discipline = 'classic_general'
        gender_age = 'general'

    if 'чемпионат россии' in t or 'чемпионат мира' in t or 'чемпионат европы' in t or 'championship' in t:
        category = 'championship'
    elif 'кубок россии' in t or 'кубок' in t or 'cup' in t or 'суперкубок' in t or 'суперлига' in t:
        category = 'cup'
    elif 'всероссийск' in t:
        category = 'all_russian'
    elif 'международн' in t or 'international' in t or 'wct' in t or 'world' in t:
        category = 'international'
    elif is_u22:
        category = 'juniors_u22'
    elif is_u19:
        category = 'youth_u19'
    elif is_u17:
        category = 'youth_u17'
    else:
        category = 'other'

    return discipline, category, gender_age

FOREIGN_COUNTRIES = {
    'sweden', 'china', 'turkey', 'belarus', 'kazakhstan', 'serbia', 'mongolia', 
    'италия', 'швеция', 'китай', 'турция', 'беларусь', 'белоруссия', 'казахстан', 
    'сербия', 'монголия', 'нигерия', 'швейцария', 'дания', 'германия', 'канада', 'норвегия',
    'italy', 'switzerland', 'norway', 'canada', 'germany', 'austria', 'czech', 'slovakia',
    'japan', 'korea', 'finland', 'denmark', 'estonia', 'latvia', 'lithuania', 'poland',
    'france', 'spain', 'usa', 'brazil', 'nigeria'
}

def is_foreign_team(team_name: str) -> bool:
    if not team_name:
        return False
    tn = team_name.lower().strip()
    for fc in FOREIGN_COUNTRIES:
        if tn == fc or tn == f"сборная {fc}" or tn.startswith(f"сборная {fc}") or tn.startswith(f"{fc} ") or tn.endswith(f" {fc}"):
            return True
        if f"({fc})" in tn or f" {fc}-" in tn or f"-{fc}" in tn:
            return True
    return False

def parse_standings_table(table) -> List[Dict]:
    if not table:
        return []
    
    rows = table.find_all('tr')
    if len(rows) < 2:
        return []

    standings = []
    
    header_row = rows[0]
    header_cells = [clean_text(th.text).lower() for th in header_row.find_all(['th', 'td'])]
    header_text = " ".join(header_cells)
    
    has_header = any(k in header_text for k in ['место', 'команда', 'состав', 'победы', 'очки', 'итоговое'])
    start_idx = 1 if has_header else 0

    for r in rows[start_idx:]:
        cells = [clean_text(td.text) for td in r.find_all(['td', 'th'])]
        if not cells or len(cells) < 2:
            continue
        
        m_place = re.search(r'(\d+)', cells[0])
        if not m_place:
            continue
        
        place = int(m_place.group(1))
        team_cell = cells[1] if len(cells) > 1 else ""
        if not team_cell:
            continue

        clean_team = clean_team_name_for_display(team_cell)
        
        # Extract players from remaining cells
        players_in_row = []
        for c in cells[2:]:
            # Check if cell has newline-separated or comma-separated players
            sub_lines = [clean_text(x) for x in re.split(r'[\n,;]+', c) if clean_text(x)]
            for sl in sub_lines:
                c_name = canonical_russian_name(sl)
                if is_valid_person_name(c_name) and len(c_name.split()) >= 2 and not any(ch.isdigit() for ch in c_name):
                    if c_name not in players_in_row:
                        players_in_row.append(c_name)

        standings.append({
            "place": place,
            "place_text": str(place),
            "team_name": clean_team or team_cell,
            "skip_name": "",
            "roster_players": players_in_row
        })

    return standings

def parse_final_results_container(container) -> List[Dict]:
    standings = []
    tables = container.find_all('table')
    for tbl in tables:
        res = parse_standings_table(tbl)
        if res and len(res) >= len(standings):
            standings = res

    if standings:
        return standings

    p_tags = container.find_all(['p', 'div', 'li'])
    for p in p_tags:
        txt = clean_text(p.text)
        m = re.match(r'^(\d+)\s*(?:место|[.\-])\s*[-–—:]?\s*(.*?)(?:\((.*?)\))?$', txt)
        if m:
            place = int(m.group(1))
            team_name = clean_team_name_for_display(m.group(2))
            if team_name:
                standings.append({
                    "place": place,
                    "place_text": str(place),
                    "team_name": team_name,
                    "skip_name": "",
                    "roster_players": []
                })
    return standings

def parse_rosters_container(container) -> List[Dict]:
    if not container:
        return []

    soup = BeautifulSoup(str(container), 'lxml')
    root = soup.find('div') or soup

    for br in root.find_all(['br', 'hr']):
        br.replace_with('\n')

    p_tags = root.find_all(['p', 'div', 'li'])
    leaf_blocks = [p for p in p_tags if not p.find(['p', 'div', 'ul', 'ol'])]
    if not leaf_blocks:
        leaf_blocks = [root]

    multi_line_blocks = [b for b in leaf_blocks if len(b.get_text(separator='\n').strip().split('\n')) >= 3]
    rosters = []

    if len(multi_line_blocks) >= 4:
        for b in multi_line_blocks:
            txt = b.get_text(separator='\n').strip()
            lines = [clean_text(l) for l in txt.split('\n') if clean_text(l)]
            if not lines:
                continue

            raw_team = lines[0]
            clean_team = clean_team_name_for_display(raw_team)

            players = []
            coach = ""

            for l in lines[1:]:
                l_low = l.lower()
                if l_low.startswith('тренер') or 'тренеры' in l_low:
                    coach = re.sub(r'^[Тт]ренер[ы:]*\s*', '', l).strip()
                    continue

                role = 'player'
                p_text = l
                if '(скип)' in l_low or '(skip)' in l_low:
                    role = 'skip'
                    p_text = re.sub(r'\s*\([Сс]кип.*?\)', '', l, flags=re.IGNORECASE).strip()
                elif '(в.-скип)' in l_low or '(вице-скип)' in l_low or '(в.скип)' in l_low:
                    role = 'vice_skip'
                    p_text = re.sub(r'\s*\([Вв][.-]?[Сс]кип.*?\)', '', l, flags=re.IGNORECASE).strip()
                elif '(запасной)' in l_low or '(зап.)' in l_low or '(зап)' in l_low:
                    role = 'alternate'
                    p_text = re.sub(r'\s*\([Зз]ап(?:асной)?\.?\)', '', l, flags=re.IGNORECASE).strip()

                c_name = canonical_russian_name(p_text)
                if is_valid_person_name(c_name) and len(c_name.split()) >= 2:
                    if not any(p["name"] == c_name for p in players):
                        players.append({"name": c_name, "role": role})

            if clean_team and (players or coach):
                rosters.append({
                    "team_name": clean_team or raw_team,
                    "skip": "",
                    "coach": coach,
                    "players": players
                })

    else:
        raw_items = []
        for tag in leaf_blocks:
            has_img = bool(tag.find('img'))
            has_strong = bool(tag.find(['strong', 'b']))
            for l in tag.get_text(separator='\n').split('\n'):
                cl = clean_text(l)
                if cl:
                    raw_items.append({"text": cl, "is_strong": has_strong, "has_img": has_img})

        current_team = None

        def finalize(t):
            if not t:
                return
            if t["team_name"] and (t["players"] or t["coach"]):
                rosters.append(t)

        for item in raw_items:
            line = item["text"]
            l_low = line.lower()

            if l_low.startswith('тренер') or 'тренеры' in l_low:
                coach_name = re.sub(r'^[Тт]ренер[ы:]*\s*', '', line).strip()
                if current_team:
                    current_team["coach"] = coach_name
                continue

            is_known_team = any(k in l_low for k in [
                'москва', 'санкт-петербург', 'краснодар', 'красноярск', 'иркутск', 'челябинск',
                'новосибирск', 'ярославль', 'самара', 'удмурт', 'кузбасс', 'свердловск', 'татарстан',
                'башкортостан', 'комсомолл', 'сборная', 'уор', 'швсм', 'сшор', 'адамант', 'москвич',
                'тисби', 'воробьевы', 'динамо', 'тилайн', 'енисей'
            ])
            
            words = line.split()
            is_person = False
            if len(words) in [2, 3]:
                w0 = words[0].lower().replace('ё', 'е')
                w1 = words[1].lower().replace('ё', 'е')
                if (w0 in ALL_FIRST_NAMES or w1 in ALL_FIRST_NAMES) and not is_known_team:
                    is_person = True

            if is_known_team or (item["is_strong"] and not is_person and len(words) <= 6) or item["has_img"]:
                if current_team and (current_team["players"] or len(rosters) > 0):
                    finalize(current_team)
                    current_team = None

                if not current_team:
                    clean_tname = clean_team_name_for_display(line)
                    current_team = {
                        "team_name": clean_tname or line,
                        "skip": "",
                        "coach": "",
                        "players": []
                    }
                    continue

            if current_team:
                role = 'player'
                p_text = line
                if '(скип)' in l_low or '(skip)' in l_low:
                    role = 'skip'
                    p_text = re.sub(r'\s*\([Сс]кип.*?\)', '', line, flags=re.IGNORECASE).strip()
                elif '(в.-скип)' in l_low or '(вице-скип)' in l_low or '(в.скип)' in l_low:
                    role = 'vice_skip'
                    p_text = re.sub(r'\s*\([Вв][.-]?[Сс]кип.*?\)', '', line, flags=re.IGNORECASE).strip()
                elif '(запасной)' in l_low or '(зап.)' in l_low or '(зап)' in l_low:
                    role = 'alternate'
                    p_text = re.sub(r'\s*\([Зз]ап(?:асной)?\.?\)', '', line, flags=re.IGNORECASE).strip()

                c_name = canonical_russian_name(p_text)
                if is_valid_person_name(c_name) and len(c_name.split()) >= 2:
                    if not any(p["name"] == c_name for p in current_team["players"]):
                        current_team["players"].append({"name": c_name, "role": role})

        finalize(current_team)

    return rosters

def parse_match_table(tbl):
    rows = tbl.find_all('tr')
    if len(rows) < 3:
        return None

    header_cells = [clean_text(c.text) for c in rows[0].find_all(['th', 'td'])]
    
    r1_cells = rows[1].find_all(['td', 'th'])
    r2_cells = rows[2].find_all(['td', 'th'])
    
    if len(r1_cells) < 3 or len(r2_cells) < 3:
        return None

    r1_html = str(r1_cells)
    r2_html = str(r2_cells)
    
    t1_has_hammer = '🔨' in r1_html or 'hammer' in r1_html.lower() or 'молот' in r1_html.lower()
    t2_has_hammer = '🔨' in r2_html or 'hammer' in r2_html.lower() or 'молот' in r2_html.lower()

    t1_texts = [clean_text(c.text) for c in r1_cells]
    t2_texts = [clean_text(c.text) for c in r2_cells]
    
    team1_name = clean_team_name_for_display(t1_texts[0])
    team2_name = clean_team_name_for_display(t2_texts[0])
    
    if not team1_name or not team2_name:
        return None
    
    if 'место' in team1_name.lower() or 'команда' in team1_name.lower():
        return None

    ends = []
    t1_score = None
    t2_score = None
    
    t1_vals = [v for v in t1_texts[1:] if v != '🔨' and v != '']
    t2_vals = [v for v in t2_texts[1:] if v != '🔨' and v != '']
    
    if t1_vals and t2_vals:
        last_t1 = t1_vals[-1]
        last_t2 = t2_vals[-1]
        if last_t1.isdigit():
            t1_score = int(last_t1)
        if last_t2.isdigit():
            t2_score = int(last_t2)
        
        end_t1_vals = t1_vals[:-1]
        end_t2_vals = t2_vals[:-1]
        
        for idx in range(min(len(end_t1_vals), len(end_t2_vals))):
            v1_raw = end_t1_vals[idx]
            v2_raw = end_t2_vals[idx]
            
            v1 = int(v1_raw) if v1_raw.isdigit() else 0
            v2 = int(v2_raw) if v2_raw.isdigit() else 0
            is_blank = 1 if (v1 == 0 and v2 == 0) else 0
            
            ends.append({
                "end_number": idx + 1,
                "team1_score": v1,
                "team2_score": v2,
                "is_blank": is_blank
            })

    winner_name = None
    if t1_score is not None and t2_score is not None:
        if t1_score > t2_score:
            winner_name = team1_name
        elif t2_score > t1_score:
            winner_name = team2_name

    sheet_id = header_cells[0] if header_cells and len(header_cells[0]) <= 2 else ""

    return {
        "match_identifier": sheet_id,
        "team1_name": team1_name,
        "team2_name": team2_name,
        "team1_hammer_start": 1 if t1_has_hammer else 0,
        "team2_hammer_start": 1 if t2_has_hammer else 0,
        "team1_total_score": t1_score,
        "team2_total_score": t2_score,
        "winner_name": winner_name,
        "ends": ends
    }

def parse_game_progress_container(container) -> Tuple[List[Dict], Dict[str, str]]:
    matches = []
    current_tour = "Матчи"
    current_stage = "group"
    team_skips_from_headings = {}
    
    elements = container.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'table'])
    
    for el in elements:
        if el.name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5']:
            txt = clean_text(el.text)
            if not txt:
                continue
            
            t_low = txt.lower()
            if 'тестов' in t_low or 'турнирная таблица' in t_low or 'схема плей-офф' in t_low:
                continue

            if any(k in t_low for k in ['тур', 'раунд', 'полуфинал', 'финал', 'квалификация', 'плей-офф', 'матч за', '1/2', '1/4']):
                current_tour = txt
                if 'финал' in t_low and 'полу' not in t_low and '1/2' not in t_low and '1/4' not in t_low:
                    current_stage = 'final'
                elif 'полуфинал' in t_low or '1/2' in t_low:
                    current_stage = 'semi'
                elif 'за 3' in t_low or 'бронз' in t_low:
                    current_stage = 'bronze'
                elif 'плей-офф' in t_low or '1/4' in t_low or 'четверть' in t_low:
                    current_stage = 'playoff'
                else:
                    current_stage = 'group'
                continue

            if ' - ' in txt or ' – ' in txt or ' — ' in txt:
                pairs = re.findall(r'([A-Za-zА-Яа-я0-9№\s\-–]+?)\s*\(([А-Яа-яA-Za-z]+)\)', txt)
                for t_raw, sk_raw in pairs:
                    t_clean = clean_team_name_for_display(re.sub(r'^[A-FА-Яа-я0-9]{1,2}\s+', '', t_raw))
                    if is_valid_person_name(sk_raw) and not any(r in sk_raw.lower() for r in ['область', 'край', 'республика', 'кузбасс']):
                        norm_key = t_clean.lower().replace(' ', '').replace('-', '').replace('№', '')
                        if len(norm_key) >= 3 and not norm_key.isdigit():
                            team_skips_from_headings[norm_key] = sk_raw

        elif el.name == 'table':
            match_data = parse_match_table(el)
            if match_data:
                if match_data["team1_total_score"] is None and match_data["team2_total_score"] is None and len(match_data["ends"]) == 0:
                    continue

                match_data["tour_name"] = current_tour
                match_data["stage_type"] = current_stage
                matches.append(match_data)

    return matches, team_skips_from_headings

def find_roster_for_team(tname: str, rosters: List[Dict]) -> Optional[Dict]:
    if not tname or not rosters:
        return None
    t_clean = clean_text(tname).lower().replace(' ', '').replace('-', '').replace('№', '')
    
    # 1. Exact match
    for r in rosters:
        r_clean = clean_text(r['team_name']).lower().replace(' ', '').replace('-', '').replace('№', '')
        if t_clean == r_clean:
            return r
            
    # 2. Number-aware match (e.g. "Москва 1" must have '1', not match 'Москва')
    t_digits = "".join([c for c in t_clean if c.isdigit()])
    for r in rosters:
        r_clean = clean_text(r['team_name']).lower().replace(' ', '').replace('-', '').replace('№', '')
        r_digits = "".join([c for c in r_clean if c.isdigit()])
        if t_digits == r_digits or (not t_digits and not r_digits):
            if t_clean in r_clean or r_clean in t_clean:
                return r

    # 3. Special aliases
    if 'комсомолл' in t_clean:
        for r in rosters:
            r_clean = clean_text(r['team_name']).lower().replace(' ', '').replace('-', '')
            r_digits = "".join([c for c in r_clean if c.isdigit()])
            if ('иркутск' in r_clean or 'комсомолл' in r_clean) and (t_digits == r_digits or (not t_digits and not r_digits)):
                return r

    # 4. Fallback descending length
    for r in sorted(rosters, key=lambda x: len(x['team_name']), reverse=True):
        r_clean = clean_text(r['team_name']).lower().replace(' ', '').replace('-', '').replace('№', '')
        if t_clean in r_clean or r_clean in t_clean:
            return r
            
    return None

def parse_tournament_html(html: str, url: str, base_title: str = "", base_date: str = "", season: int = None):
    soup = BeautifulSoup(html, 'lxml')
    
    title = base_title
    h1 = soup.find('h1')
    if h1 and h1.text.strip():
        title = clean_text(h1.text)
    elif not title and soup.title:
        title = clean_text(soup.title.text.split('|')[0].replace('Федерация Кёрлинга России', ''))
    
    if not title:
        title = "Турнир"

    if not season:
        m_year = re.search(r'20\d{2}', title)
        if m_year:
            season = int(m_year.group(0))
        else:
            season = 2024

    discipline, category, gender_age = detect_discipline_and_category(title)

    pdf_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '.pdf' in href.lower():
            if not href.startswith('http'):
                href = f"https://curling.ru{href}" if href.startswith('/') else f"https://curling.ru/{href}"
            pdf_name = clean_text(a.text) or "Документ турнира (PDF)"
            pdf_links.append({"title": pdf_name, "url": href})

    containers = soup.select('.bl-rezult-tab-container')
    game_progress_cont = None
    participating_teams_cont = None
    final_results_cont = None
    
    for c in containers:
        cid = c.get('id', '').lower()
        if any(k in cid for k in ['course-tournament', 'game-progress', 'hod-turnira', 'raspisanie', 'tab-progress']):
            game_progress_cont = c
        elif any(k in cid for k in ['participating-teams', 'teams', 'komandy', 'uchastniki']):
            participating_teams_cont = c
        elif any(k in cid for k in ['final-results', 'results', 'rezultaty', 'itog']):
            final_results_cont = c

    # 1. Parse Rosters
    rosters = []
    if participating_teams_cont:
        rosters = parse_rosters_container(participating_teams_cont)

    # 2. Parse Matches and extract skips from match pairings
    matches = []
    match_skips_map = {}
    if game_progress_cont:
        matches, match_skips_map = parse_game_progress_container(game_progress_cont)
    else:
        all_tables = soup.find_all('table')
        for tbl in all_tables:
            m = parse_match_table(tbl)
            if m and (m["team1_total_score"] is not None or len(m["ends"]) > 0):
                m["tour_name"] = "Матчи"
                m["stage_type"] = "group"
                matches.append(m)

    # Also scan entire page text for "Команда (Скип)"
    full_page_text = soup.get_text("\n")
    for line in full_page_text.split('\n'):
        m_skip = re.search(r'([А-Яа-яA-Za-z0-9\s\-№]+?)\s*\(([А-Яа-яA-Za-z]+)\)', line)
        if m_skip:
            t_cand = clean_text(m_skip.group(1)).lower().replace(' ', '').replace('-', '').replace('№', '')
            s_cand = clean_text(m_skip.group(2))
            if len(t_cand) >= 3 and is_valid_person_name(s_cand) and not t_cand.isdigit():
                if t_cand not in match_skips_map:
                    match_skips_map[t_cand] = s_cand

    # 3. If rosters are empty, try to build them from standings
    standings = []
    if final_results_cont:
        standings = parse_final_results_container(final_results_cont)
    
    if not standings:
        all_tables = soup.find_all('table')
        for tbl in all_tables:
            res = parse_standings_table(tbl)
            if res and len(res) > len(standings):
                standings = res

    if not rosters and standings:
        for st in standings:
            if st.get('roster_players'):
                p_objs = [{"name": p, "role": "player"} for p in st['roster_players']]
                rosters.append({
                    "team_name": st['team_name'],
                    "skip": "",
                    "coach": st.get('coach', ''),
                    "players": p_objs
                })

    # 4. Match Skips from match headings into Rosters
    clean_skips_map = {}
    for k, v in match_skips_map.items():
        if len(k) >= 3 and not k.isdigit():
            clean_skips_map[k] = v

    for r in rosters:
        r_tname = clean_text(r['team_name']).lower().replace(' ', '').replace('-', '').replace('№', '')
        r_digits = "".join([c for c in r_tname if c.isdigit()])
        
        assigned_skip = None
        
        # Priority 1: Check if any player's surname matches a skip paired with this specific team
        for p in r['players']:
            p_surname = p['name'].split()[0].lower().replace('ё', 'е')
            for k_team, s_name in clean_skips_map.items():
                s_norm = s_name.lower().replace('ё', 'е')
                k_digits = "".join([c for c in k_team if c.isdigit()])
                if s_norm == p_surname:
                    if (r_digits == k_digits or not r_digits or not k_digits) and (k_team in r_tname or r_tname in k_team or ('комсомолл' in k_team and 'иркутск' in r_tname)):
                        assigned_skip = p
                        break
            if assigned_skip:
                break
                
        # Priority 2: Match by surname in clean_skips_map across whole roster
        if not assigned_skip:
            for p in r['players']:
                p_surname = p['name'].split()[0].lower().replace('ё', 'е')
                for k_team, s_name in clean_skips_map.items():
                    s_norm = s_name.lower().replace('ё', 'е')
                    if s_norm == p_surname:
                        assigned_skip = p
                        break
                if assigned_skip:
                    break
                    
        if assigned_skip:
            r['skip'] = assigned_skip['name']
            for p in r['players']:
                p['role'] = 'skip' if p['name'] == assigned_skip['name'] else 'player'
        else:
            for p in r['players']:
                if p['role'] == 'skip':
                    r['skip'] = p['name']
                    break
            if not r.get('skip') and r.get('players'):
                r['skip'] = r['players'][0]['name']
                r['players'][0]['role'] = 'skip'

    # 5. Attach exact verified skips to every match row
    for m in matches:
        r1 = find_roster_for_team(m['team1_name'], rosters)
        r2 = find_roster_for_team(m['team2_name'], rosters)
        
        m['team1_skip'] = r1['skip'].split()[0] if (r1 and r1.get('skip')) else ""
        m['team2_skip'] = r2['skip'].split()[0] if (r2 and r2.get('skip')) else ""

    # Synchronize standings with clean roster names and verified skips
    for st in standings:
        matched_roster = find_roster_for_team(st['team_name'], rosters)
        if matched_roster:
            st['team_name'] = matched_roster['team_name']
            st['skip_name'] = matched_roster['skip']
            st['roster_players'] = [p['name'] for p in matched_roster['players']]
            if matched_roster.get('coach'):
                st['coach'] = matched_roster['coach']

    return {
        "url": url,
        "title": title,
        "season": season,
        "date_display": clean_text(base_date),
        "discipline": discipline,
        "category": category,
        "gender_age": gender_age,
        "pdf_links": pdf_links,
        "standings": standings,
        "rosters": rosters,
        "matches": matches
    }
