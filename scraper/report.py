"""Build a summary report and detect price changes against the last trusted run."""
from html import escape

import pandas as pd

from scraper import config


def _run(conn, run_id):
    """One row of the runs table as a dict, or None."""
    cur = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
    row = cur.fetchone()
    return dict(zip([c[0] for c in cur.description], row)) if row else None


def _baseline(conn, run_id):
    """The latest earlier run that is complete and not simulated, or None."""
    cur = conn.execute(
        """
        SELECT * FROM runs
        WHERE id < ? AND complete = 1 AND simulated = 0
        ORDER BY id DESC LIMIT 1
        """,
        (run_id,),
    )
    row = cur.fetchone()
    return dict(zip([c[0] for c in cur.description], row)) if row else None


def _snapshot(conn, run_id):
    return pd.read_sql_query(
        """
        SELECT b.url, b.title, b.rating, h.price, h.in_stock
        FROM price_history h JOIN books b ON b.url = h.url
        WHERE h.run_id = ?
        """,
        conn,
        params=(run_id,),
    )


def build_report(conn, run_id):
    """Return a dict with summary stats and changes vs the baseline run.
    new/removed are None when they were skipped as unreliable."""
    run = _run(conn, run_id)
    if run is None:
        return None
    baseline = _baseline(conn, run_id)

    current = _snapshot(conn, run_id)
    report = {
        "run": run["started_at"],
        "run_id": run_id,
        "complete": bool(run["complete"]),
        "simulated": bool(run["simulated"]),
        "pages": run["pages"],
        "baseline_run": baseline["started_at"] if baseline else None,
        "warnings": [],
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

    if report["simulated"]:
        report["warnings"].append("Simulated prices: demo only, never used as a baseline")
    if not report["complete"]:
        report["warnings"].append(
            f"Incomplete run ({run['pages']} pages): new/removed lists skipped"
        )

    if baseline:
        previous = _snapshot(conn, baseline["id"])
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

        if not report["complete"]:
            report["new"] = report["removed"] = None
        elif len(current) < len(previous) * (1 - config.SUSPECT_DROP_RATIO):
            report["removed"] = None
            report["warnings"].append(
                f"Book count dropped from {len(previous)} to {len(current)} "
                f"(more than {config.SUSPECT_DROP_RATIO:.0%}); the site layout may have changed. "
                "Removed list skipped"
            )

    return report


def _count(items):
    return "skipped" if items is None else len(items)


def format_text(r):
    lines = [
        f"Book Price Report — run {r['run']}",
        "=" * 50,
        *[f"⚠ {w}" for w in r["warnings"]],
        *([""] if r["warnings"] else []),
        f"Books scraped : {r['count']}  (in stock: {r['in_stock']})",
        f"Price (GBP)   : avg £{r['avg_price']:.2f}  min £{r['min_price']:.2f}  max £{r['max_price']:.2f}",
        "Ratings       : " + "  ".join(f"{k}★ {v}" for k, v in r["ratings"].items()),
        "",
        "Cheapest 5-star books:",
        *[f"  £{b['price']:>6.2f}  {b['title']}" for b in r["cheap_five_star"]],
        "",
    ]
    if not r["baseline_run"]:
        lines.append("No complete baseline run yet — nothing to compare.")
        return "\n".join(lines)

    lines.append(f"Changes since {r['baseline_run']}:")
    for label, key in (("Price increases", "increases"), ("Price drops", "drops")):
        lines.append(f"  {label}: {len(r[key])}")
        for c in r[key]:
            lines.append(f"    £{c['price_old']:.2f} -> £{c['price']:.2f} ({c['change']:+.2f})  {c['title']}")
    lines.append(f"  New books: {_count(r['new'])}")
    lines.extend(f"    + {t}" for t in (r["new"] or [])[:10])
    lines.append(f"  Removed books: {_count(r['removed'])}")
    lines.extend(f"    - {t}" for t in (r["removed"] or [])[:10])
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

    warnings = ""
    if r["warnings"]:
        items = "".join(f"<li>{escape(w)}</li>" for w in r["warnings"])
        warnings = f"<ul style='background:#fff3cd;padding:8px 24px'>{items}</ul>"

    cheap = "".join(f"<li>£{b['price']:.2f} — {escape(b['title'])}</li>" for b in r["cheap_five_star"])
    html = f"""
    <h2>Book Price Report</h2>
    {warnings}
    <p>Run: {r['run']}</p>
    <ul>
      <li>Books scraped: <b>{r['count']}</b> (in stock: {r['in_stock']})</li>
      <li>Average price: £{r['avg_price']:.2f} (min £{r['min_price']:.2f}, max £{r['max_price']:.2f})</li>
    </ul>
    <h3>Cheapest 5-star books</h3><ul>{cheap}</ul>
    """
    if r["baseline_run"]:
        html += f"""
        <p>Changes since {r['baseline_run']}</p>
        <h3>Price increases ({len(r['increases'])})</h3>{change_rows(r['increases'])}
        <h3>Price drops ({len(r['drops'])})</h3>{change_rows(r['drops'])}
        <p>New books: {_count(r['new'])} &nbsp; Removed books: {_count(r['removed'])}</p>
        """
    else:
        html += "<p>No complete baseline run yet — nothing to compare.</p>"
    return html
