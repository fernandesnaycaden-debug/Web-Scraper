"""Build a summary report and detect price changes between the last two runs."""
from html import escape

import pandas as pd


def _runs(conn):
    """Timestamps of the latest two runs (newest first)."""
    rows = conn.execute(
        "SELECT DISTINCT scraped_at FROM price_history ORDER BY scraped_at DESC LIMIT 2"
    ).fetchall()
    return [r[0] for r in rows]


def _snapshot(conn, run):
    return pd.read_sql_query(
        """
        SELECT b.url, b.title, b.rating, h.price, h.in_stock
        FROM price_history h JOIN books b ON b.url = h.url
        WHERE h.scraped_at = ?
        """,
        conn,
        params=(run,),
    )


def build_report(conn):
    """Return a dict with summary stats and changes vs the previous run."""
    runs = _runs(conn)
    if not runs:
        return None

    current = _snapshot(conn, runs[0])
    report = {
        "run": runs[0],
        "previous_run": runs[1] if len(runs) > 1 else None,
        "count": len(current),
        "avg_price": current["price"].mean(),
        "min_price": current["price"].min(),
        "max_price": current["price"].max(),
        "in_stock": int(current["in_stock"].sum()),
        "ratings": current["rating"].value_counts().sort_index().to_dict(),
        "cheap_five_star": current[current["rating"] == 5]
            .nsmallest(5, "price")[["title", "price"]].to_dict("records"),
        "increases": [], "drops": [], "new": [], "removed": [],
    }

    if report["previous_run"]:
        previous = _snapshot(conn, runs[1])
        merged = current.merge(
            previous[["url", "price"]], on="url", how="outer",
            suffixes=("", "_old"), indicator=True,
        )
        both = merged[merged["_merge"] == "both"].copy()
        both["change"] = both["price"] - both["price_old"]
        cols = ["title", "price_old", "price", "change"]
        report["increases"] = both[both["change"] > 0].sort_values("change", ascending=False)[cols].to_dict("records")
        report["drops"] = both[both["change"] < 0].sort_values("change")[cols].to_dict("records")
        report["new"] = merged[merged["_merge"] == "left_only"]["title"].tolist()
        # Removed books aren't in the current snapshot, so look up their titles.
        removed_urls = merged[merged["_merge"] == "right_only"]["url"]
        report["removed"] = previous[previous["url"].isin(removed_urls)]["title"].tolist()

    return report


def format_text(r):
    lines = [
        f"Book Price Report — run {r['run']}",
        "=" * 50,
        f"Books scraped : {r['count']}  (in stock: {r['in_stock']})",
        f"Price (GBP)   : avg £{r['avg_price']:.2f}  min £{r['min_price']:.2f}  max £{r['max_price']:.2f}",
        "Ratings       : " + "  ".join(f"{k}★ {v}" for k, v in r["ratings"].items()),
        "",
        "Cheapest 5-star books:",
        *[f"  £{b['price']:>6.2f}  {b['title']}" for b in r["cheap_five_star"]],
        "",
    ]
    if not r["previous_run"]:
        lines.append("First run — no previous data to compare yet.")
        return "\n".join(lines)

    lines.append(f"Changes since {r['previous_run']}:")
    for label, key in (("Price increases", "increases"), ("Price drops", "drops")):
        lines.append(f"  {label}: {len(r[key])}")
        for c in r[key]:
            lines.append(f"    £{c['price_old']:.2f} -> £{c['price']:.2f} ({c['change']:+.2f})  {c['title']}")
    lines.append(f"  New books: {len(r['new'])}")
    lines.extend(f"    + {t}" for t in r["new"][:10])
    lines.append(f"  Removed books: {len(r['removed'])}")
    lines.extend(f"    - {t}" for t in r["removed"][:10])
    return "\n".join(lines)


def format_html(r):
    def change_rows(items):
        if not items:
            return "<p><em>None</em></p>"
        rows = "".join(
            f"<tr><td>{escape(c['title'])}</td><td>£{c['price_old']:.2f}</td>"
            f"<td>£{c['price']:.2f}</td><td>{c['change']:+.2f}</td></tr>"
            for c in items
        )
        return f"<table border='1' cellpadding='4' cellspacing='0'><tr><th>Title</th><th>Old</th><th>New</th><th>Change</th></tr>{rows}</table>"

    cheap = "".join(f"<li>£{b['price']:.2f} — {escape(b['title'])}</li>" for b in r["cheap_five_star"])
    html = f"""
    <h2>Book Price Report</h2>
    <p>Run: {r['run']}</p>
    <ul>
      <li>Books scraped: <b>{r['count']}</b> (in stock: {r['in_stock']})</li>
      <li>Average price: £{r['avg_price']:.2f} (min £{r['min_price']:.2f}, max £{r['max_price']:.2f})</li>
    </ul>
    <h3>Cheapest 5-star books</h3><ul>{cheap}</ul>
    """
    if r["previous_run"]:
        html += f"""
        <h3>Price increases ({len(r['increases'])})</h3>{change_rows(r['increases'])}
        <h3>Price drops ({len(r['drops'])})</h3>{change_rows(r['drops'])}
        <p>New books: {len(r['new'])} &nbsp; Removed books: {len(r['removed'])}</p>
        """
    else:
        html += "<p>First run — no previous data to compare yet.</p>"
    return html
