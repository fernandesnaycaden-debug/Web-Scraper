from datetime import datetime

from scraper.clean import clean_books

RAW = [
    {"title": "  Book A ", "url": "u1", "price": "£51.77", "rating": "Three", "availability": "In stock"},
    {"title": "Book B", "url": "u2", "price": "Â£10.00", "rating": "Five", "availability": "Out of stock"},
    {"title": "Book A dup", "url": "u1", "price": "£51.77", "rating": "Three", "availability": "In stock"},
    {"title": "Bad", "url": "u3", "price": "N/A", "rating": "One", "availability": "In stock"},
]


def test_clean_types_and_values():
    df = clean_books(RAW, scraped_at=datetime(2026, 1, 1))
    assert list(df["url"]) == ["u1", "u2"]          # duplicate and unparseable price dropped
    assert df.loc[0, "title"] == "Book A"           # whitespace stripped
    assert df.loc[0, "price"] == 51.77
    assert df.loc[1, "price"] == 10.00              # mojibake "Â£" handled
    assert list(df["rating"]) == [3, 5]
    assert list(df["in_stock"]) == [True, False]
    assert (df["scraped_at"] == "2026-01-01T00:00:00").all()


def test_empty_input():
    assert clean_books([]).empty
