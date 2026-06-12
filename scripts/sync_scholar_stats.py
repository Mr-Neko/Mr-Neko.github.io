#!/usr/bin/env python3
"""
Daily Google Scholar citation sync.
Fetches the public Scholar profile, recomputes total citations / h-index / i10-index
by summing per-paper citation counts, appends a history point, and updates
scholar_stats.json. Intended to be run once per day by a scheduled task.
"""
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

SCHOLAR_ID = "SkV_NNsAAAAJ"
SCHOLAR_URL = f"https://scholar.google.com/citations?user={SCHOLAR_ID}&hl=en&cstart=0&pagesize=100"
STATS_PATH = Path(__file__).resolve().parent.parent / "scholar_stats.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse_citation_counts(html: str):
    """Extract per-paper citation counts from the works table."""
    # Each paper row has a 'gsc_a_ac' cell containing the citation count (or empty).
    cells = re.findall(r'class="gsc_a_ac[^"]*"[^>]*>(\d*)<', html)
    counts = [int(c) for c in cells if c.strip().isdigit()]
    return counts


def compute_metrics(counts):
    total = sum(counts)
    s = sorted(counts, reverse=True)
    h = 0
    for i, c in enumerate(s, 1):
        if c >= i:
            h = i
    i10 = sum(1 for c in counts if c >= 10)
    return total, h, i10


def main():
    try:
        html = fetch_html(SCHOLAR_URL)
    except Exception as e:
        print(f"ERROR: failed to fetch Scholar page: {e}", file=sys.stderr)
        return 1

    counts = parse_citation_counts(html)
    if not counts:
        print("ERROR: no citation counts parsed (page layout changed or blocked).",
              file=sys.stderr)
        return 2

    total, h, i10 = compute_metrics(counts)
    today = date.today().isoformat()

    if STATS_PATH.exists():
        stats = json.loads(STATS_PATH.read_text())
    else:
        stats = {"scholar_id": SCHOLAR_ID, "history": []}

    stats["total_citations"] = total
    stats["h_index"] = h
    stats["i10_index"] = i10
    stats["last_updated"] = today

    history = stats.get("history", [])
    # Replace today's point if it already exists, else append.
    history = [p for p in history if p.get("date") != today]
    history.append({"date": today, "citations": total})
    # Keep at most last 60 points.
    stats["history"] = history[-60:]

    STATS_PATH.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")
    print(f"OK: {today} citations={total} h={h} i10={i10} (papers={len(counts)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
