"""Data cleaning with pandas."""
from datetime import datetime

import pandas as pd

RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def clean_books(raw_books, scraped_at=None):
    """Turn raw scraped dicts into a tidy, typed DataFrame."""
    columns = ["url", "title", "price", "rating", "in_stock", "scraped_at"]
    if not raw_books:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(raw_books)

    df["title"] = df["title"].str.strip()
    # "£51.77" (or mis-decoded "Â£51.77") -> 51.77
    df["price"] = pd.to_numeric(
        df["price"].str.replace(r"[^\d.]", "", regex=True), errors="coerce"
    )
    df["rating"] = df["rating"].map(RATING_WORDS).astype("Int64")
    df["in_stock"] = df["availability"].str.contains("In stock", case=False, na=False)
    df["scraped_at"] = (scraped_at or datetime.now()).isoformat(timespec="seconds")

    df = df.dropna(subset=["price"]).drop_duplicates(subset="url")
    return df[columns].reset_index(drop=True)
