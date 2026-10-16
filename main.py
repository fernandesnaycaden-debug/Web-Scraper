"""Scrape books.toscrape.com -> clean -> store -> report -> (optionally) email."""
import argparse
import logging
import random
import sys
from datetime import datetime

from scraper import config
from scraper.clean import clean_books
from scraper.fetch import Fetcher
from scraper.notify import send_report
from scraper.parse import parse_listing
from scraper.report import build_report, format_html, format_text
from scraper.storage import connect, export_csv, save_run

log = logging.getLogger("scraper")


def setup_logging():
    # Windows consoles default to cp1252, which can't print "★" and crashes.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(config.LOG_DIR / "scraper.log", encoding="utf-8"),
        ],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def scrape(max_pages=None):
    """Walk the paginated catalogue and return raw book dicts."""
    books, url, page = [], config.START_URL, 0
    with Fetcher() as fetcher:
        while url and (max_pages is None or page < max_pages):
            page += 1
            html = fetcher.get(url)
            if html is None:
                log.error("Stopping at page %d: could not fetch %s", page, url)
                break
            page_books, url = parse_listing(html, url)
            books.extend(page_books)
            log.info("Page %d: %d books (total %d)", page, len(page_books), len(books))
    return books


def simulate_changes(df, n=5):
    """Nudge a few prices so price-change tracking has something to show.
    books.toscrape.com never changes its prices, so this is demo-only."""
    idx = random.sample(range(len(df)), min(n, len(df)))
    for i in idx:
        df.loc[i, "price"] = round(df.loc[i, "price"] * random.uniform(0.8, 1.2), 2)
    log.info("Simulated price changes on %d books", len(idx))
    return df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pages", type=int, help="only scrape the first N pages")
    parser.add_argument("--email", action="store_true", help="email the report")
    parser.add_argument("--simulate-changes", action="store_true",
                        help="randomly change a few prices (demo price tracking)")
    parser.add_argument("--no-csv", action="store_true", help="skip CSV export")
    args = parser.parse_args()

    setup_logging()
    log.info("Starting scrape of %s", config.BASE_URL)

    raw = scrape(args.max_pages)
    df = clean_books(raw, scraped_at=datetime.now())
    if df.empty:
        log.error("No books scraped; nothing to save")
        return 1
    if args.simulate_changes:
        df = simulate_changes(df)

    conn = connect()
    try:
        log.info("Saved %d rows to %s", save_run(conn, df), config.DB_PATH)
        if not args.no_csv:
            log.info("Exported CSV to %s", export_csv(df))

        report = build_report(conn)
    finally:
        conn.close()

    text = format_text(report)
    print("\n" + text)

    if args.email:
        changes = len(report["increases"]) + len(report["drops"])
        subject = f"Book Price Report: {report['count']} books, {changes} price changes"
        send_report(subject, text, format_html(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
