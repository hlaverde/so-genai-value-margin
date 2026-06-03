import argparse
import gzip
from collections import Counter
from pathlib import Path

import pandas as pd

from src.data.build_gharchive_entry_panel import loads_json
from src.paths import PROCESSED_DIR, ensure_directories
from src.utils.io import write_csv
from src.utils.logging_utils import get_logger


DEFAULT_ENTRY_SAMPLE_EVENTS = {
    "PullRequestEvent",
    "IssuesEvent",
    "IssueCommentEvent",
    "ForkEvent",
    "WatchEvent",
}


def iter_files(input_dirs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for input_dir in input_dirs:
        files.extend(sorted(input_dir.glob("*.json.gz")))
    return sorted(files)


def parse_event_types(value: str | None) -> set[str]:
    if value is None:
        return set(DEFAULT_ENTRY_SAMPLE_EVENTS)
    return {item.strip() for item in value.split(",") if item.strip()}


def build_entry_repo_sample(
    input_dirs: list[Path],
    event_types: set[str],
    top_per_event: int,
    top_overall: int,
) -> pd.DataFrame:
    files = iter_files(input_dirs)
    if not files:
        raise FileNotFoundError("No .json.gz files found in input dirs")

    repo_event_counts = Counter()
    repo_total_counts = Counter()
    repo_names: dict[int, str] = {}

    for path in files:
        with gzip.open(path, "rb") as handle:
            for line in handle:
                event = loads_json(line)
                event_type = event.get("type")
                if event_type not in event_types:
                    continue
                repo = event.get("repo") or {}
                repo_id = repo.get("id")
                repo_name = repo.get("name")
                if repo_id is None or repo_name is None:
                    continue
                repo_id = int(repo_id)
                repo_names[repo_id] = str(repo_name)
                repo_event_counts[(repo_id, event_type)] += 1
                repo_total_counts[repo_id] += 1

    selected: set[int] = set()
    for event_type in sorted(event_types):
        counts = Counter({repo_id: count for (repo_id, et), count in repo_event_counts.items() if et == event_type})
        selected.update(repo_id for repo_id, _count in counts.most_common(top_per_event))

    selected.update(repo_id for repo_id, _count in repo_total_counts.most_common(top_overall))

    rows = []
    for repo_id in selected:
        row = {
            "repo_id": repo_id,
            "repo_name": repo_names.get(repo_id),
            "entry_events": repo_total_counts.get(repo_id, 0),
        }
        for event_type in sorted(event_types):
            row[event_type] = repo_event_counts.get((repo_id, event_type), 0)
        rows.append(row)

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["event_types_observed"] = (out[list(sorted(event_types))] > 0).sum(axis=1)
    out = out.sort_values(["entry_events", "event_types_observed", "repo_name"], ascending=[False, False, True])
    return out.reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select GH Archive repositories using entry-oriented event types.")
    parser.add_argument("--input-dir", type=Path, action="append", required=True)
    parser.add_argument("--event-types", default=None, help="Comma-separated event types. Defaults to PR/issues/forks/watch/comments.")
    parser.add_argument("--top-per-event", type=int, default=300)
    parser.add_argument("--top-overall", type=int, default=1000)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROCESSED_DIR / "gharchive" / "entry_oriented_repos_sample_2021_2024.csv",
    )
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    event_types = parse_event_types(args.event_types)
    logger.info("Selecting repositories using event types: %s", ", ".join(sorted(event_types)))
    out = build_entry_repo_sample(args.input_dir, event_types, args.top_per_event, args.top_overall)
    write_csv(out, args.output)
    logger.info("Wrote %s repositories to %s", len(out), args.output)
    if not out.empty:
        logger.info("\n%s", out.head(25).to_string(index=False))


if __name__ == "__main__":
    main()
