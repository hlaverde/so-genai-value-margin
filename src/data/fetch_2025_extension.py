"""Quota-bounded 2025 panel extension (the reviewers' "biggest lever").

No API key is available, so the IP quota is 300 requests/day. A full
100-tag 2025 panel is infeasible under that cap, so we fetch a
stratified subset of tags spanning the AI-answerability range (excluding
the handful of mega-volume tags that would exhaust the budget) for all
of calendar 2025, quarter by quarter, with a hard request budget and the
API's backoff respected. Output schema is identical to the SEDE/API
pipeline, so the rows append directly to the existing panel.

Reuses parsing/schema helpers from fetch_stackoverflow_via_api (Rule 2).
Output: data/processed/so_2025_extension_raw.csv
"""
from __future__ import annotations
import sys, time, csv
from datetime import datetime, timezone
from pathlib import Path
import requests
import pandas as pd

THIS = Path(__file__).resolve(); ROOT = THIS.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.paths import PROCESSED_DIR  # noqa: E402
from src.data.fetch_stackoverflow_via_api import (  # noqa: E402
    API_BASE, DEFAULT_FILTER_ID, OUTPUT_COLUMNS, question_to_rows,
)

AI_REAL = PROCESSED_DIR / "ai_answerability_real.csv"
OUT = PROCESSED_DIR / "so_2025_extension_raw.csv"
MAX_REQUESTS = 285          # hard budget (IP quota is 300/day)
PAGES_PER_WINDOW = 8        # cap paging per (tag, quarter)
PAGESIZE = 100

# Mega-volume tags to exclude so the budget covers a broad subset.
MEGA = {"python", "javascript", "java", "c#", "android", "html", "css",
        "php", "node.js", "reactjs", "python-3.x", "sql", "c++", "r"}

QUARTERS = [("2025-01-01", "2025-04-01"), ("2025-04-01", "2025-07-01"),
            ("2025-07-01", "2025-10-01"), ("2025-10-01", "2026-01-01")]


def ts(s):
    return int(datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def pick_subset():
    ai = pd.read_csv(AI_REAL)
    ai = ai[~ai["tag"].isin(MEGA)].copy()
    # stratify: sort by structural answerability, take an even spread of ~30
    ai = ai.sort_values("ai_answerability_structural").reset_index(drop=True)
    n = min(30, len(ai))
    idx = [round(i * (len(ai) - 1) / (n - 1)) for i in range(n)]
    return ai.loc[idx, "tag"].tolist()


def main():
    tags = pick_subset()
    print(f"[2025] subset of {len(tags)} tags: {tags}", flush=True)
    sess = requests.Session()
    n_req = 0
    rows = []
    stop = False
    for tag in tags:
        if stop:
            break
        for (d0, d1) in QUARTERS:
            if stop:
                break
            for page in range(1, PAGES_PER_WINDOW + 1):
                if n_req >= MAX_REQUESTS:
                    print(f"[2025] budget reached ({n_req} req); stopping", flush=True)
                    stop = True
                    break
                params = dict(site="stackoverflow", tagged=tag,
                              fromdate=ts(d0), todate=ts(d1),
                              pagesize=PAGESIZE, page=page, order="asc",
                              sort="creation", filter=DEFAULT_FILTER_ID)
                try:
                    r = sess.get(f"{API_BASE}/questions", params=params, timeout=40)
                    n_req += 1
                    if r.status_code != 200:
                        print(f"  [{tag} {d0} p{page}] HTTP {r.status_code}; skip", flush=True)
                        break
                    j = r.json()
                except Exception as e:
                    print(f"  [{tag} {d0} p{page}] ERR {type(e).__name__}; skip", flush=True)
                    break
                for q in j.get("items", []):
                    rows.extend(question_to_rows(q))
                qr = j.get("quota_remaining")
                if j.get("backoff"):
                    time.sleep(j["backoff"] + 1)
                if not j.get("has_more"):
                    break
                if qr is not None and qr < 8:
                    print(f"[2025] quota low ({qr}); stopping", flush=True)
                    stop = True
                    break
            print(f"  [{tag} {d0}] cum_req={n_req} rows={len(rows)}", flush=True)
    # keep only 2025 rows (subset tags) and write
    df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS).drop_duplicates(
        ["question_id", "tag"])
    df = df[df["week_start"].str[:4] == "2025"]
    df.to_csv(OUT, index=False)
    print(f"[2025] DONE: {n_req} requests, {len(df):,} unique (q,tag) rows, "
          f"{df['tag'].nunique()} tags -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
