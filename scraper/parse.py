"""HTML parsing: turn a listing page into a list of raw book dicts."""
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


def parse_listing(html, page_url):
    """Return (books, next_page_url). next_page_url is None on the last page."""
    soup = BeautifulSoup(html, "lxml")
    books = []

    for card in soup.select("article.product_pod"):
        try:
            link = card.select_one("h3 a")
            rating_tag = card.select_one("p.star-rating")
            # class looks like ["star-rating", "Three"]; take the word that isn't "star-rating"
            rating = next((c for c in rating_tag["class"] if c != "star-rating"), None)
            books.append({
                "title": link["title"],
                "url": urljoin(page_url, link["href"]),
                "price": card.select_one(".price_color").get_text(strip=True),
                "rating": rating,
                "availability": card.select_one(".availability").get_text(strip=True),
            })
        except (AttributeError, KeyError, TypeError) as e:
            # One broken card shouldn't kill the whole page.
            log.warning("Skipping malformed book card on %s: %s", page_url, e)

    next_link = soup.select_one("li.next a")
    next_url = urljoin(page_url, next_link["href"]) if next_link else None
    return books, next_url
