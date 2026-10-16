"""Persistence: SQLite for history, CSV for easy viewing."""
import sqlite3
from datetime import date

import pandas as pd

from scraper import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    url         TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    rating      INTEGER,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS price_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT NOT NULL REFERENCES books(url),
    price       REAL NOT NULL,
    in_stock    INTEGER NOT NULL,
    scraped_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_url_time ON price_history(url, scraped_at);
"""


def connect(db_path=None):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path or config.DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def save_run(conn, df):
    """Upsert books and append this run's prices. Returns the number of rows saved."""
    rows = df.to_dict("records")
    with conn:  # one transaction for the whole run
        conn.executemany(
            """
            INSERT INTO books (url, title, rating, first_seen, last_seen)
            VALUES (:url, :title, :rating, :scraped_at, :scraped_at)
            ON CONFLICT(url) DO UPDATE SET
                title = excluded.title,
                rating = excluded.rating,
                last_seen = excluded.last_seen
            """,
            [{**r, "rating": None if pd.isna(r["rating"]) else int(r["rating"])} for r in rows],
        )
        conn.executemany(
            """
            INSERT INTO price_history (url, price, in_stock, scraped_at)
            VALUES (:url, :price, :in_stock, :scraped_at)
            """,
            [{**r, "in_stock": int(r["in_stock"])} for r in rows],
        )
    return len(rows)


def export_csv(df):
    config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.EXPORT_DIR / f"books_{date.today().isoformat()}.csv"
    df.to_csv(path, index=False, encoding="utf-8")
    return path
