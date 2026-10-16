from datetime import datetime

import pytest

from scraper.clean import clean_books
from scraper.report import build_report, format_html, format_text
from scraper.storage import connect, save_run


def raw(n, price=10.0, overrides=None):
    """n books u0..u{n-1}; overrides maps index -> price."""
    overrides = overrides or {}
    return [
        {"title": f"Book {i}", "url": f"u{i}", "price": f"£{overrides.get(i, price):.2f}",
         "rating": "Five", "availability": "In stock"}
        for i in range(n)
    ]


@pytest.fixture
def conn():
    c = connect(":memory:")
    yield c
    c.close()


def run(conn, books, day, *, complete=True, simulated=False):
    started = datetime(2026, 1, day)
    df = clean_books(books, scraped_at=started)
    return save_run(conn, df, started_at=started, pages=1, complete=complete,
                    simulated=simulated, max_pages=None if complete else 1)


def test_price_increase_and_drop(conn):
    run(conn, raw(4), 1)
    rid = run(conn, raw(4, overrides={0: 12.0, 1: 7.5}), 2)
    r = build_report(conn, rid)
    assert [(c["title"], c["change"]) for c in r["increases"]] == [("Book 0", 2.0)]
    assert [(c["title"], c["change"]) for c in r["drops"]] == [("Book 1", -2.5)]
    assert r["new"] == [] and r["removed"] == [] and r["warnings"] == []
    assert r["baseline_run"] == "2026-01-01T00:00:00"
    assert "Changes since 2026-01-01T00:00:00" in format_text(r)
    format_html(r)


def test_incomplete_run_skips_removed(conn):
    run(conn, raw(10), 1)
    rid = run(conn, raw(5, overrides={0: 11.0}), 2, complete=False)
    r = build_report(conn, rid)
    assert not r["removed"] and not r["new"]
    assert r["complete"] is False
    assert any(w.startswith("Incomplete run") for w in r["warnings"])
    assert len(r["increases"]) == 1          # price changes still reported
    assert "Removed books: skipped" in format_text(r)


def test_incomplete_run_is_never_a_baseline(conn):
    run(conn, raw(10), 1)
    run(conn, raw(5), 2, complete=False)
    rid = run(conn, raw(10), 3)
    r = build_report(conn, rid)
    assert r["baseline_run"] == "2026-01-01T00:00:00"
    assert r["new"] == [] and r["removed"] == []
    assert r["warnings"] == []


def test_simulated_run_is_never_a_baseline(conn):
    run(conn, raw(10), 1)
    sim = run(conn, raw(10, overrides={0: 15.0, 1: 5.0}), 2, simulated=True)
    assert any(w.startswith("Simulated prices") for w in build_report(conn, sim)["warnings"])
    r = build_report(conn, run(conn, raw(10), 3))
    assert r["baseline_run"] == "2026-01-01T00:00:00"
    assert r["increases"] == [] and r["drops"] == []
    assert r["new"] == [] and r["removed"] == []


def test_suspect_drop_skips_removed(conn):
    run(conn, raw(100), 1)
    r = build_report(conn, run(conn, raw(80), 2))
    assert r["removed"] is None
    assert any("dropped from 100 to 80" in w for w in r["warnings"])


def test_first_run_has_no_baseline(conn):
    r = build_report(conn, run(conn, raw(3), 1))
    assert r["baseline_run"] is None
    assert "No complete baseline" in format_text(r)
