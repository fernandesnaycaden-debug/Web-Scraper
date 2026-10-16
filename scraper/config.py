"""Central settings. Everything tweakable lives here."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# --- Target site ---
BASE_URL = "https://books.toscrape.com/"
START_URL = BASE_URL + "catalogue/page-1.html"

# --- Polite fetching ---
USER_AGENT = "BookPriceScraper/1.0 (learning project; +https://github.com/)"
MIN_DELAY = 1.0        # seconds between requests (lower bound)
MAX_DELAY = 2.0        # seconds between requests (upper bound, random jitter)
TIMEOUT = 10.0         # seconds per request
MAX_RETRIES = 3        # retries on 429 / 5xx / network errors
BACKOFF_BASE = 2.0     # wait 2s, 4s, 8s... between retries

# --- Report ---
SUSPECT_DROP_RATIO = 0.10  # a complete run this much smaller than the baseline is suspect

# --- Paths ---
DATA_DIR = ROOT / "data"
EXPORT_DIR = DATA_DIR / "exports"
DB_PATH = DATA_DIR / "scraper.db"
LOG_DIR = ROOT / "logs"

# --- Email (read from .env) ---
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")
