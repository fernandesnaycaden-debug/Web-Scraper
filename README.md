# Book Price Scraper → Data Report

Scrapes all ~1000 books from [books.toscrape.com](https://books.toscrape.com) (a sandbox site built for scraping practice), cleans the data with pandas, stores price history in SQLite, exports a CSV, and produces a report of price changes since the last run. It can run daily and email the report.

**Skills shown:** HTTP (httpx), HTML parsing (BeautifulSoup), data cleaning (pandas), SQL (SQLite), error handling, polite scraping, scheduling, SMTP.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Usage

```powershell
python main.py                      # full scrape (~50 pages, ~1.5 min because of polite delays)
python main.py --max-pages 2        # quick test run
python main.py --simulate-changes   # randomly tweak a few prices to demo change tracking
python main.py --email              # email the report (needs .env, see below)
python main.py --no-csv             # skip the CSV export
pytest                              # offline tests against a saved HTML page
```

Outputs:
- `data/scraper.db`: SQLite tables `books` (one row per book) and `price_history` (one row per book per run)
- `data/exports/books_YYYY-MM-DD.csv`: a snapshot of the latest run
- `logs/scraper.log`: the run log

> books.toscrape.com never changes its prices, so the change report will be empty on real runs. Use `--simulate-changes` on a second run to see increases and drops.

## Polite scraping

- Checks `robots.txt` before every request
- Sends an identifying User-Agent
- Waits a random 1–2 s between requests
- Uses a 10 s timeout and retries 429/5xx/network errors up to 3 times with exponential backoff, honouring `Retry-After`
- A bad page or malformed listing is logged and skipped. It doesn't crash the run.

## Email setup

1. Copy `.env.example` to `.env`.
2. For Gmail, enable 2-Step Verification, then create an [App Password](https://myaccount.google.com/apppasswords) and put it in `SMTP_PASSWORD`.
3. Test it with `python main.py --max-pages 1 --email`.

## Daily schedule (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File .\schedule_task.ps1 -Time "08:00"
Start-ScheduledTask -TaskName BookPriceScraper     # run once now to test
Unregister-ScheduledTask -TaskName BookPriceScraper -Confirm:$false   # remove
```

## Project layout

```
scraper/
  config.py   settings (URLs, delays, paths, email from .env)
  fetch.py    HTTP client: robots.txt, rate limiting, retries
  parse.py    BeautifulSoup: listing page -> book dicts + next-page link
  clean.py    pandas: prices to float, ratings to 1–5, dedupe
  storage.py  SQLite upsert + history, CSV export
  report.py   summary stats + diff vs previous run (text and HTML)
  notify.py   SMTP email
main.py       CLI that ties it all together
```

## Example queries

```sql
-- price history for one book
SELECT scraped_at, price FROM price_history WHERE url LIKE '%a-light-in-the-attic%';

-- average price by rating (latest run)
SELECT b.rating, ROUND(AVG(h.price), 2)
FROM price_history h JOIN books b USING (url)
WHERE h.scraped_at = (SELECT MAX(scraped_at) FROM price_history)
GROUP BY b.rating;
```
