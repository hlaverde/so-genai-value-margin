import argparse
import gzip
import json
from pathlib import Path

import pandas as pd

from src.paths import INTERIM_DIR, RAW_DIR, ensure_directories
from src.utils.io import write_csv
from src.utils.logging_utils import get_logger


EVENT_TYPES = {
    "PushEvent",
    "PullRequestEvent",
    "IssuesEvent",
    "IssueCommentEvent",
    "ForkEvent",
    "CreateEvent",
    "WatchEvent",
}


def read_events(paths: list[Path]) -> pd.DataFrame:
    rows = []
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                event = json.loads(line)
                if event.get("type") not in EVENT_TYPES:
                    continue
                rows.append(
                    {
                        "event_id": event.get("id"),
                        "event_type": event.get("type"),
                        "created_at": event.get("created_at"),
                        "actor_id": (event.get("actor") or {}).get("id"),
                        "actor_login": (event.get("actor") or {}).get("login"),
                        "repo_id": (event.get("repo") or {}).get("id"),
                        "repo_name": (event.get("repo") or {}).get("name"),
                    }
                )
    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean selected GH Archive hourly files into a compact event table.")
    parser.add_argument("--input-dir", type=Path, default=RAW_DIR / "gharchive")
    parser.add_argument("--output", type=Path, default=INTERIM_DIR / "gharchive_events.csv")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    paths = sorted(args.input_dir.glob("*.json.gz"))
    if not paths:
        raise FileNotFoundError(f"No GH Archive .json.gz files found in {args.input_dir}")
    out = read_events(paths)
    write_csv(out, args.output)
    logger.info("Wrote %s cleaned GitHub events to %s", len(out), args.output)


if __name__ == "__main__":
    main()
