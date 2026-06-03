import argparse
import gzip
from collections import Counter
from pathlib import Path

import pandas as pd

from src.data.build_gharchive_entry_panel import ENTRY_EVENT_TYPES, loads_json
from src.paths import PROCESSED_DIR, RAW_DIR, ensure_directories
from src.utils.io import write_csv
from src.utils.logging_utils import get_logger


def iter_files(input_dirs: list[Path]) -> list[Path]:
    paths = []
    for input_dir in input_dirs:
        paths.extend(sorted(input_dir.glob("*.json.gz")))
    return sorted(paths)


def build_top_repos(input_dirs: list[Path], top_n: int) -> pd.DataFrame:
    repo_events = Counter()
    repo_event_type = Counter()
    files = iter_files(input_dirs)
    if not files:
        raise FileNotFoundError("No .json.gz files found in input dirs")

    for path in files:
        with gzip.open(path, "rb") as handle:
            for line in handle:
                event = loads_json(line)
                event_type = event.get("type")
                if event_type not in ENTRY_EVENT_TYPES:
                    continue
                repo = event.get("repo") or {}
                repo_id = repo.get("id")
                repo_name = repo.get("name")
                if repo_id is None or repo_name is None:
                    continue
                key = (int(repo_id), str(repo_name))
                repo_events[key] += 1
                repo_event_type[(int(repo_id), str(repo_name), event_type)] += 1

    rows = []
    for (repo_id, repo_name), events in repo_events.most_common(top_n):
        row = {"repo_id": repo_id, "repo_name": repo_name, "events": events}
        for event_type in sorted(ENTRY_EVENT_TYPES):
            row[event_type] = repo_event_type.get((repo_id, repo_name, event_type), 0)
        rows.append(row)
    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find most active repositories in sampled GH Archive files.")
    parser.add_argument("--input-dir", type=Path, action="append", required=True)
    parser.add_argument("--top-n", type=int, default=500)
    parser.add_argument("--output", type=Path, default=PROCESSED_DIR / "gharchive" / "top_repos_sample_2021_2024.csv")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    out = build_top_repos(args.input_dir, args.top_n)
    write_csv(out, args.output)
    logger.info("Wrote top repos to %s", args.output)
    logger.info("\n%s", out.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
