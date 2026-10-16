"""Persistence: SQLite for history, CSV for easy viewing."""
import sqlite3
from datetime import date, datetime

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
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    pages       INTEGER NOT NULL,
    books       INTEGER NOT NULL,
    complete    INTEGER NOT NULL,
    simulated   INTEGER NOT NULL DEFAULT 0,
    max_pages   INTEGER
);
CREATE TABLE IF NOT EXISTS price_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT NOT NULL REFERENCES books(url),
    price       REAL NOT NULL,
    in_stock    INTEGER NOT NULL,
    scraped_at  TEXT NOT NULL,
    run_id      INTEGER REFERENCES runs(id)
);
CREATE INDEX IF NOT EXISTS idx_history_url_time ON price_history(url, scraped_at);
"""

# Created after migration: on an old database run_id doesn't exist until then.
RUN_INDEX = "CREATE INDEX IF NOT EXISTS idx_history_run ON price_history(run_id)"


def connect(db_path=None):
    if db_path is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path or config.DB_PATH)
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn):
    """Give pre-runs databases a run_id: one complete run per distinct scraped_at."""
    columns = [row[1] for row in conn.execute("PRAGMA table_info(price_history)")]
    if "run_id" not in columns:
        conn.execute("BEGIN")
        try:
            conn.execute("ALTER TABLE price_history ADD COLUMN run_id INTEGER REFERENCES runs(id)")
            conn.execute(
                """
                INSERT INTO runs (started_at, finished_at, pages, books, complete, simulated)
                SELECT scraped_at, scraped_at, 0, COUNT(*), 1, 0
                FROM price_history GROUP BY scraped_at ORDER BY scraped_at
                """
            )
            conn.execute(
                """
                UPDATE price_history
                SET run_id = (SELECT id FROM runs WHERE runs.started_at = price_history.scraped_at)
                """
            )
            conn.execute(RUN_INDEX)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    conn.execute(RUN_INDEX)


def save_run(conn, df, *, started_at, pages, complete, simulated=False, max_pages=None):
    """Record the run, upsert books and append its prices in one transaction. Returns the run id."""
    rows = df.to_dict("records")
    with conn:  # one transaction for the whole run
        run_id = conn.execute(
            """
            INSERT INTO runs (started_at, finished_at, pages, books, complete, simulated, max_pages)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                started_at.isoformat(timespec="seconds"),
                datetime.now().isoformat(timespec="seconds"),
                pages, len(rows), int(complete), int(simulated), max_pages,
            ),
        ).lastrowid
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
            INSERT INTO price_history (url, price, in_stock, scraped_at, run_id)
            VALUES (:url, :price, :in_stock, :scraped_at, :run_id)
            """,
            [{**r, "in_stock": int(r["in_stock"]), "run_id": run_id} for r in rows],
        )
    return run_id


def export_csv(df):
    config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.EXPORT_DIR / f"books_{date.today().isoformat()}.csv"
    df.to_csv(path, index=False, encoding="utf-8")
    return path
