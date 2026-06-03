import argparse
import gzip
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.build_gharchive_entry_panel import ENTRY_EVENT_TYPES, loads_json
from src.paths import PROCESSED_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


def iter_files(input_dirs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for input_dir in input_dirs:
        files.extend(sorted(input_dir.glob("*.json.gz")))
    return sorted(files)


def week_start_from_created_at(created_at: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(created_at, tz="UTC")
    return (timestamp - pd.to_timedelta(timestamp.dayofweek, unit="D")).normalize().tz_localize(None)


def parse_event_types(value: str | None) -> set[str]:
    if value is None:
        return set(ENTRY_EVENT_TYPES)
    return {item.strip() for item in value.split(",") if item.strip()}


def load_repo_language(metadata_path: Path, top_repos_path: Path) -> pd.DataFrame:
    metadata = read_csv(metadata_path)
    top_repos = read_csv(top_repos_path)
    keep_cols = ["repo_id", "repo_name"]
    for optional_col in ["events", "entry_events"]:
        if optional_col in top_repos.columns:
            keep_cols.append(optional_col)
    top_repos = top_repos[keep_cols].drop_duplicates(subset=["repo_id", "repo_name"])
    metadata = metadata[metadata["http_status"].eq(200)].copy()
    metadata = metadata[metadata["primary_language"].notna()].copy()
    out = top_repos.merge(metadata[["repo_name", "primary_language", "owner_type", "fork", "archived"]], on="repo_name", how="inner")
    out["primary_language"] = out["primary_language"].astype(str).str.lower()
    return out


def event_row(
    event: dict[str, Any],
    repo_language: dict[int, str],
    event_types: set[str],
) -> tuple[int, str, str, int | None] | None:
    event_type = event.get("type")
    if event_type not in event_types:
        return None
    repo = event.get("repo") or {}
    repo_id = repo.get("id")
    if repo_id is None:
        return None
    repo_id = int(repo_id)
    language = repo_language.get(repo_id)
    if language is None:
        return None
    actor = event.get("actor") or {}
    actor_id = actor.get("id")
    return repo_id, language, str(event_type), int(actor_id) if actor_id is not None else None


def build_language_panel(input_dirs: list[Path], repo_language_df: pd.DataFrame, event_types: set[str]) -> pd.DataFrame:
    repo_language = dict(zip(repo_language_df["repo_id"].astype(int), repo_language_df["primary_language"].astype(str)))
    files = iter_files(input_dirs)
    if not files:
        raise FileNotFoundError("No .json.gz files found in input dirs")

    events = defaultdict(int)
    active_actors: dict[tuple[str, pd.Timestamp, str], set[int]] = defaultdict(set)
    first_seen_actor_language: set[tuple[int, str]] = set()
    first_seen_actor_language_event: set[tuple[int, str, str]] = set()
    first_seen_counts = defaultdict(int)
    first_seen_event_counts = defaultdict(int)

    for path in files:
        with gzip.open(path, "rb") as handle:
            for line in handle:
                raw_event = loads_json(line)
                parsed = event_row(raw_event, repo_language, event_types)
                if parsed is None:
                    continue
                _repo_id, language, event_type, actor_id = parsed
                week_start = week_start_from_created_at(raw_event["created_at"])
                key = (language, week_start, event_type)
                events[key] += 1
                if actor_id is not None:
                    active_actors[key].add(actor_id)
                    actor_language_key = (actor_id, language)
                    if actor_language_key not in first_seen_actor_language:
                        first_seen_actor_language.add(actor_language_key)
                        first_seen_counts[(language, week_start, event_type)] += 1
                    actor_event_key = (actor_id, language, event_type)
                    if actor_event_key not in first_seen_actor_language_event:
                        first_seen_actor_language_event.add(actor_event_key)
                        first_seen_event_counts[(language, week_start, event_type)] += 1

    rows = []
    for key, event_count in events.items():
        language, week_start, event_type = key
        rows.append(
            {
                "language": language,
                "week_start": week_start,
                "event_type": event_type,
                "events": event_count,
                "active_actors": len(active_actors.get(key, set())),
                "first_seen_actors_language": first_seen_counts.get(key, 0),
                "first_seen_actors_language_event": first_seen_event_counts.get(key, 0),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["language", "week_start", "event_type"]).reset_index(drop=True)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a language-week GH Archive panel from top repositories with metadata.")
    parser.add_argument("--input-dir", type=Path, action="append", required=True)
    parser.add_argument("--top-repos", type=Path, default=PROCESSED_DIR / "gharchive" / "top_repos_sample_2021_2024.csv")
    parser.add_argument("--metadata", type=Path, default=PROCESSED_DIR / "gharchive" / "top_repos_github_metadata.csv")
    parser.add_argument("--event-types", default=None, help="Comma-separated event types to keep. Defaults to all baseline GH Archive event types.")
    parser.add_argument("--output", type=Path, default=PROCESSED_DIR / "gharchive" / "gharchive_top_repo_language_week_event_panel.csv")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    repo_language = load_repo_language(args.metadata, args.top_repos)
    event_types = parse_event_types(args.event_types)
    logger.info("Loaded %s repositories with public primary language metadata", len(repo_language))
    logger.info("Keeping event types: %s", ", ".join(sorted(event_types)))
    out = build_language_panel(args.input_dir, repo_language, event_types)
    write_csv(out, args.output)
    logger.info("Wrote %s rows to %s", len(out), args.output)
    if not out.empty:
        logger.info("\n%s", out.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
