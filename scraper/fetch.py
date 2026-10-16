"""HTTP layer: polite, rate-limited fetching with retries."""
import logging
import random
import time
from urllib import robotparser
from urllib.parse import urljoin

import httpx

from scraper import config

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}


class Fetcher:
    """Wraps an httpx.Client with robots.txt checks, delays and retries."""

    def __init__(self):
        self.client = httpx.Client(
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.TIMEOUT,
            follow_redirects=True,
        )
        self._last_request = 0.0
        self.robots = self._load_robots()

    def _load_robots(self):
        rp = robotparser.RobotFileParser()
        robots_url = urljoin(config.BASE_URL, "/robots.txt")
        try:
            resp = self.client.get(robots_url)
            # A missing robots.txt (404) means everything is allowed.
            rp.parse(resp.text.splitlines() if resp.status_code == 200 else [])
        except httpx.HTTPError as e:
            log.warning("Could not read robots.txt (%s); assuming allowed", e)
            rp.parse([])
        return rp

    def _wait_politely(self):
        delay = random.uniform(config.MIN_DELAY, config.MAX_DELAY)
        elapsed = time.monotonic() - self._last_request
        if elapsed < delay:
            time.sleep(delay - elapsed)

    def get(self, url):
        """Return page HTML, or None if the page could not be fetched."""
        if not self.robots.can_fetch(config.USER_AGENT, url):
            log.warning("robots.txt disallows %s; skipping", url)
            return None

        for attempt in range(1, config.MAX_RETRIES + 2):
            self._wait_politely()
            self._last_request = time.monotonic()
            try:
                resp = self.client.get(url)
            except httpx.HTTPError as e:
                wait = config.BACKOFF_BASE ** attempt
                log.warning("Network error on %s (%s); retry in %.0fs", url, e, wait)
            else:
                if resp.status_code == 200:
                    # The site serves UTF-8; force it so "£" doesn't become "Â£".
                    resp.encoding = "utf-8"
                    return resp.text
                if resp.status_code not in RETRY_STATUSES:
                    log.error("HTTP %s on %s; giving up", resp.status_code, url)
                    return None
                wait = _retry_after(resp) or config.BACKOFF_BASE ** attempt
                log.warning("HTTP %s on %s; retry in %.0fs", resp.status_code, url, wait)

            if attempt > config.MAX_RETRIES:
                break
            time.sleep(wait)

        log.error("Failed to fetch %s after %d retries", url, config.MAX_RETRIES)
        return None

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _retry_after(resp):
    """Parse a numeric Retry-After header, if the server sent one."""
    value = resp.headers.get("Retry-After", "")
    return float(value) if value.isdigit() else None
