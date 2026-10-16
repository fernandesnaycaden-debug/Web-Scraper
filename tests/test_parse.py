from pathlib import Path

from scraper.parse import parse_listing

FIXTURE = Path(__file__).parent / "fixtures" / "page1.html"
PAGE_URL = "https://books.toscrape.com/catalogue/page-1.html"


def test_parses_twenty_books():
    books, _ = parse_listing(FIXTURE.read_text(encoding="utf-8"), PAGE_URL)
    assert len(books) == 20


def test_first_book_fields():
    books, _ = parse_listing(FIXTURE.read_text(encoding="utf-8"), PAGE_URL)
    first = books[0]
    assert first["title"] == "A Light in the Attic"
    assert first["price"] == "£51.77"
    assert first["rating"] == "Three"
    assert "In stock" in first["availability"]
    assert first["url"].startswith("https://books.toscrape.com/catalogue/")


def test_next_page_link():
    _, next_url = parse_listing(FIXTURE.read_text(encoding="utf-8"), PAGE_URL)
    assert next_url == "https://books.toscrape.com/catalogue/page-2.html"


def test_last_page_has_no_next():
    html = "<html><body><article class='product_pod'></article></body></html>"
    books, next_url = parse_listing(html, PAGE_URL)
    assert books == []  # malformed card is skipped, not a crash
    assert next_url is None
