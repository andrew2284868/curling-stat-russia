import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "curling_data.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS tournaments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        season INTEGER,
        date_start TEXT,
        date_end TEXT,
        date_display TEXT,
        discipline TEXT,
        category TEXT,
        gender_age TEXT,
        location TEXT,
        tier TEXT,
        tier_name TEXT,
        base_points INTEGER DEFAULT 250,
        source_type TEXT,
        pdf_links_json TEXT,
        raw_html TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        clean_name TEXT NOT NULL,
        region TEXT,
        skip_name TEXT,
        discipline TEXT,
        category TEXT,
        fcf_points REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(clean_name, discipline)
    );

    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        gender TEXT,
        region TEXT,
        birth_year INTEGER,
        fcf_points REAL DEFAULT 0.0,
        elo_rating REAL DEFAULT 1500.0,
        matches_played INTEGER DEFAULT 0,
        matches_won INTEGER DEFAULT 0,
        matches_lost INTEGER DEFAULT 0,
        win_rate REAL DEFAULT 0.0,
        gold_medals INTEGER DEFAULT 0,
        silver_medals INTEGER DEFAULT 0,
        bronze_medals INTEGER DEFAULT 0,
        ends_played INTEGER DEFAULT 0,
        ends_won INTEGER DEFAULT 0,
        hammer_conversion_rate REAL DEFAULT 0.0,
        steal_rate REAL DEFAULT 0.0,
        force_rate REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(full_name)
    );

    CREATE TABLE IF NOT EXISTS tournament_teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        team_id INTEGER NOT NULL,
        team_display_name TEXT NOT NULL,
        skip_name TEXT,
        final_place INTEGER,
        place_text TEXT,
        coach TEXT,
        group_name TEXT,
        group_place TEXT,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        points REAL DEFAULT 0,
        FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
        FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE,
        UNIQUE(tournament_id, team_display_name)
    );

    CREATE TABLE IF NOT EXISTS team_rosters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_team_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        role TEXT,
        order_index INTEGER DEFAULT 0,
        FOREIGN KEY(tournament_team_id) REFERENCES tournament_teams(id) ON DELETE CASCADE,
        FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE,
        UNIQUE(tournament_team_id, player_id)
    );

    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        tour_name TEXT,
        stage_type TEXT,
        match_identifier TEXT,
        match_date TEXT,
        sheet TEXT,
        team1_name TEXT NOT NULL,
        team2_name TEXT NOT NULL,
        team1_id INTEGER,
        team2_id INTEGER,
        team1_skip TEXT,
        team2_skip TEXT,
        team1_hammer_start INTEGER DEFAULT 0,
        team2_hammer_start INTEGER DEFAULT 0,
        team1_total_score INTEGER,
        team2_total_score INTEGER,
        winner_team_id INTEGER,
        winner_name TEXT,
        is_finished INTEGER DEFAULT 1,
        FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS match_ends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER NOT NULL,
        end_number INTEGER NOT NULL,
        team1_score INTEGER DEFAULT 0,
        team2_score INTEGER DEFAULT 0,
        team_with_hammer INTEGER,
        is_blank INTEGER DEFAULT 0,
        FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE,
        UNIQUE(match_id, end_number)
    );

    CREATE TABLE IF NOT EXISTS player_ratings_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER NOT NULL,
        tournament_id INTEGER,
        match_id INTEGER,
        date TEXT,
        old_rating REAL,
        new_rating REAL,
        rating_change REAL,
        FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS player_discipline_stats (
        player_id INTEGER NOT NULL,
        discipline TEXT NOT NULL,
        fcf_points REAL DEFAULT 0.0,
        elo_rating REAL DEFAULT 1500.0,
        matches_played INTEGER DEFAULT 0,
        matches_won INTEGER DEFAULT 0,
        matches_lost INTEGER DEFAULT 0,
        win_rate REAL DEFAULT 0.0,
        gold_medals INTEGER DEFAULT 0,
        silver_medals INTEGER DEFAULT 0,
        bronze_medals INTEGER DEFAULT 0,
        is_skip INTEGER DEFAULT 0,
        PRIMARY KEY(player_id, discipline),
        FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_tournaments_season ON tournaments(season);
    CREATE INDEX IF NOT EXISTS idx_tournaments_discipline ON tournaments(discipline);
    CREATE INDEX IF NOT EXISTS idx_players_rating ON players(elo_rating DESC);
    CREATE INDEX IF NOT EXISTS idx_matches_tourn ON matches(tournament_id);
    CREATE INDEX IF NOT EXISTS idx_match_ends_match ON match_ends(match_id);
    CREATE INDEX IF NOT EXISTS idx_p_disc_points ON player_discipline_stats(discipline, fcf_points DESC);
    CREATE INDEX IF NOT EXISTS idx_p_disc_elo ON player_discipline_stats(discipline, elo_rating DESC);
    ''')
    conn.commit()
    conn.close()
    print("Database initialized successfully at", DB_PATH)

if __name__ == "__main__":
    init_db()
