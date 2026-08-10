import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "curling_data.db")
SQL_OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "curling_export_postgres.sql")

def export_sqlite_to_postgres_sql():
    """
    Exports the entire SQLite database to a PostgreSQL compatible SQL file.
    Includes table definitions with Postgres data types (SERIAL, TEXT, INTEGER, DOUBLE PRECISION, TIMESTAMP)
    and batch INSERT statements.
    """
    if not os.path.exists(DB_PATH):
        print(f"SQLite DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tables = [
        "tournaments",
        "teams",
        "players",
        "tournament_teams",
        "team_rosters",
        "matches",
        "match_ends",
        "player_ratings_history"
    ]

    print(f"[PostgreSQL Export] Reading SQLite DB and generating {SQL_OUTPUT_PATH}...")

    with open(SQL_OUTPUT_PATH, "w", encoding="utf-8") as out:
        out.write("-- =========================================================\n")
        out.write("-- PostgreSQL Database Schema & Data Export for CurlingStat\n")
        out.write("-- Target: https://curling.ru/ Russian Curling Federation (2016-2026)\n")
        out.write("-- =========================================================\n\n")
        out.write("BEGIN;\n\n")

        # Postgres DDL
        out.write("""
DROP TABLE IF EXISTS player_ratings_history CASCADE;
DROP TABLE IF EXISTS match_ends CASCADE;
DROP TABLE IF EXISTS matches CASCADE;
DROP TABLE IF EXISTS team_rosters CASCADE;
DROP TABLE IF EXISTS tournament_teams CASCADE;
DROP TABLE IF EXISTS players CASCADE;
DROP TABLE IF EXISTS teams CASCADE;
DROP TABLE IF EXISTS tournaments CASCADE;

CREATE TABLE tournaments (
    id SERIAL PRIMARY KEY,
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
    source_type TEXT,
    pdf_links_json TEXT,
    raw_html TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    clean_name TEXT NOT NULL,
    region TEXT,
    skip_name TEXT,
    discipline TEXT,
    category TEXT,
    UNIQUE(clean_name, discipline)
);

CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    full_name TEXT NOT NULL UNIQUE,
    normalized_name TEXT NOT NULL,
    gender TEXT,
    elo_rating DOUBLE PRECISION DEFAULT 1500.0,
    matches_played INTEGER DEFAULT 0,
    matches_won INTEGER DEFAULT 0,
    matches_lost INTEGER DEFAULT 0,
    win_rate DOUBLE PRECISION DEFAULT 0.0,
    gold_medals INTEGER DEFAULT 0,
    silver_medals INTEGER DEFAULT 0,
    bronze_medals INTEGER DEFAULT 0,
    ends_played INTEGER DEFAULT 0,
    ends_won INTEGER DEFAULT 0,
    hammer_conversion_rate DOUBLE PRECISION DEFAULT 0.0,
    steal_rate DOUBLE PRECISION DEFAULT 0.0,
    force_rate DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tournament_teams (
    id SERIAL PRIMARY KEY,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    team_display_name TEXT NOT NULL,
    skip_name TEXT,
    final_place INTEGER,
    place_text TEXT,
    coach TEXT,
    group_name TEXT,
    group_place TEXT,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    points DOUBLE PRECISION DEFAULT 0,
    UNIQUE(tournament_id, team_display_name)
);

CREATE TABLE team_rosters (
    id SERIAL PRIMARY KEY,
    tournament_team_id INTEGER NOT NULL REFERENCES tournament_teams(id) ON DELETE CASCADE,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    role TEXT,
    order_index INTEGER DEFAULT 0,
    UNIQUE(tournament_team_id, player_id)
);

CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
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
    is_finished INTEGER DEFAULT 1
);

CREATE TABLE match_ends (
    id SERIAL PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    end_number INTEGER NOT NULL,
    team1_score INTEGER DEFAULT 0,
    team2_score INTEGER DEFAULT 0,
    team_with_hammer INTEGER,
    is_blank INTEGER DEFAULT 0,
    UNIQUE(match_id, end_number)
);

CREATE TABLE player_ratings_history (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    tournament_id INTEGER,
    match_id INTEGER,
    date TEXT,
    old_rating DOUBLE PRECISION,
    new_rating DOUBLE PRECISION,
    rating_change DOUBLE PRECISION
);

CREATE INDEX idx_tournaments_season ON tournaments(season);
CREATE INDEX idx_tournaments_discipline ON tournaments(discipline);
CREATE INDEX idx_players_rating ON players(elo_rating DESC);
CREATE INDEX idx_matches_tourn ON matches(tournament_id);
CREATE INDEX idx_match_ends_match ON match_ends(match_id);

""")

        # Data Dump
        for tbl in tables:
            cursor.execute(f"SELECT * FROM {tbl}")
            rows = cursor.fetchall()
            if not rows:
                continue

            columns = [desc[0] for desc in cursor.description]
            cols_str = ", ".join([f'"{col}"' for col in columns])
            
            out.write(f"\n-- Data for table: {tbl} ({len(rows)} rows)\n")
            
            # Batch inserts in chunks of 500
            chunk_size = 500
            for i in range(0, len(rows), chunk_size):
                chunk = rows[i:i + chunk_size]
                val_lines = []
                for row in chunk:
                    row_vals = []
                    for val in row:
                        if val is None:
                            row_vals.append("NULL")
                        elif isinstance(val, (int, float)):
                            row_vals.append(str(val))
                        else:
                            # Escape single quotes
                            escaped = str(val).replace("'", "''")
                            row_vals.append(f"'{escaped}'")
                    val_lines.append(f"({', '.join(row_vals)})")
                
                insert_stmt = f"INSERT INTO {tbl} ({cols_str}) VALUES\n" + ",\n".join(val_lines) + "\nON CONFLICT DO NOTHING;\n"
                out.write(insert_stmt)

        out.write("\nCOMMIT;\n")

    conn.close()
    file_size_mb = os.path.getsize(SQL_OUTPUT_PATH) / (1024 * 1024)
    print(f"[PostgreSQL Export] Successfully exported to {SQL_OUTPUT_PATH} ({file_size_mb:.2f} MB)")

if __name__ == "__main__":
    export_sqlite_to_postgres_sql()
