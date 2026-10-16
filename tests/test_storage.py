import sqlite3
from datetime import datetime

import pytest

from scraper.clean import clean_books
from scraper.storage import connect, save_run

OLD_SCHEMA = """
CREATE TABLE books (
    url TEXT PRIMARY KEY, title TEXT NOT NULL, rating INTEGER,
    first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
CREATE TABLE price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL REFERENCES books(url),
    price REAL NOT NULL, in_stock INTEGER NOT NULL, scraped_at TEXT NOT NULL
);
"""

RAW = [
    {"title": "Book A", "url": "u1", "price": "£10.00", "rating": "One", "availability": "In stock"},
    {"title": "Book B", "url": "u2", "price": "£20.00", "rating": "Two", "availability": "In stock"},
]


def test_connect_in_memory():
    conn = connect(":memory:")
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"books", "runs", "price_history"} <= tables
    conn.close()


def test_migration_backfills_runs(tmp_path):
    db = tmp_path / "old.db"
    old = sqlite3.connect(db)
    old.executescript(OLD_SCHEMA)
    old.executemany("INSERT INTO books VALUES (?, ?, NULL, 't1', 't2')", [("u1", "A"), ("u2", "B")])
    old.executemany(
        "INSERT INTO price_history (url, price, in_stock, scraped_at) VALUES (?, ?, 1, ?)",
        [("u1", 10, "t1"), ("u2", 20, "t1"), ("u1", 11, "t2")],
    )
    old.commit()
    old.close()

    connect(db).close()
    conn = connect(db)  # second migration must be a no-op
    assert conn.execute("SELECT started_at, books, complete, simulated FROM runs ORDER BY id").fetchall() == [
        ("t1", 2, 1, 0), ("t2", 1, 1, 0),
    ]
    assert conn.execute("SELECT COUNT(*) FROM price_history WHERE run_id IS NULL").fetchone()[0] == 0
    conn.close()


def test_save_run_is_atomic():
    conn = connect(":memory:")
    conn.execute(
        "CREATE TRIGGER fail BEFORE INSERT ON price_history BEGIN SELECT RAISE(ABORT, 'boom'); END"
    )
    started = datetime(2026, 1, 1)
    with pytest.raises(sqlite3.IntegrityError):
        save_run(conn, clean_books(RAW, scraped_at=started), started_at=started,
                 pages=1, complete=True, simulated=False, max_pages=None)
    assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0
    conn.close()
