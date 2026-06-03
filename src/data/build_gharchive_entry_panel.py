import argparse
import gzip
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from src.paths import INTERIM_DIR, PROCESSED_DIR, RAW_DIR, ensure_directories
from src.utils.io import write_csv
from src.utils.logging_utils import get_logger

try:
    import orjson

    def loads_json(line: str):
        return orjson.loads(line)

except ImportError:
    import json

    def loads_json(line: str):
        return json.loads(line)


ENTRY_EVENT_TYPES = {
    "PushEvent",
    "PullRequestEvent",
    "IssuesEvent",
    "IssueCommentEvent",
    "ForkEvent",
    "CreateEvent",
    "WatchEvent",
}


def parse_time(value: str) -> pd.Timestamp:
    return pd.to_datetime(value, utc=True).tz_convert(None)


def week_start(ts: pd.Timestamp) -> pd.Timestamp:
    return (ts - pd.to_timedelta(ts.weekday(), unit="D")).normalize()


def file_hour(path: Path) -> int:
    return int(path.stem.split("-")[-1].replace(".json", ""))


def select_paths(input_dir: Path, hours: set[int] | None = None, max_files: int | None = None) -> list[Path]:
    paths = sorted(input_dir.glob("*.json.gz"))
    if hours is not None:
        paths = [p for p in paths if file_hour(p) in hours]
    if max_files is not None:
        paths = paths[:max_files]
    return paths


def iter_events(paths: list[Path]):
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                event = loads_json(line)
                event_type = event.get("type")
                if event_type not in ENTRY_EVENT_TYPES:
                    continue
                actor = event.get("actor") or {}
                repo = event.get("repo") or {}
                actor_id = actor.get("id")
                repo_id = repo.get("id")
                created_at = event.get("created_at")
                if actor_id is None or repo_id is None or not created_at:
                    continue
                yield {
                    "event_type": event_type,
                    "created_at": created_at,
                    "actor_id": actor_id,
                    "actor_login": actor.get("login"),
                    "repo_id": repo_id,
                    "repo_name": repo.get("name"),
                }


def build_window_panel(
    input_dir: Path,
    window_name: str,
    hours: set[int] | None = None,
    max_files: int | None = None,
    include_repo_panel: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    paths = select_paths(input_dir, hours=hours, max_files=max_files)
    if not paths:
        raise FileNotFoundError(f"No GH Archive files found in {input_dir}")

    event_counts = Counter()
    repo_counts = Counter()
    unique_repos = set()
    first_seen_actor: dict[int, pd.Timestamp] = {}
    first_event_type: dict[int, str] = {}
    actor_events = Counter()
    total_events = 0

    for event in iter_events(paths):
        total_events += 1
        ts = parse_time(event["created_at"])
        wk = week_start(ts)
        event_type = event["event_type"]
        actor_id = int(event["actor_id"])
        repo_id = int(event["repo_id"])
        repo_name = event["repo_name"]

        event_counts[(window_name, wk, event_type)] += 1
        unique_repos.add(repo_id)
        if include_repo_panel:
            repo_counts[(window_name, wk, repo_id, repo_name, event_type)] += 1
        actor_events[(window_name, wk, actor_id, event_type)] += 1

        if actor_id not in first_seen_actor or ts < first_seen_actor[actor_id]:
            first_seen_actor[actor_id] = ts
            first_event_type[actor_id] = event_type

    event_rows = [
        {
            "window": window,
            "week_start": wk.date().isoformat(),
            "event_type": event_type,
            "events": count,
        }
        for (window, wk, event_type), count in event_counts.items()
    ]
    event_panel = pd.DataFrame(event_rows).sort_values(["window", "week_start", "event_type"])

    if include_repo_panel:
        repo_rows = [
            {
                "window": window,
                "week_start": wk.date().isoformat(),
                "repo_id": repo_id,
                "repo_name": repo_name,
                "event_type": event_type,
                "events": count,
            }
            for (window, wk, repo_id, repo_name, event_type), count in repo_counts.items()
        ]
        repo_panel = pd.DataFrame(repo_rows).sort_values(["window", "week_start", "repo_id", "event_type"])
    else:
        repo_panel = pd.DataFrame()

    actor_week_first = defaultdict(set)
    actor_week_events = Counter()
    for (window, wk, actor_id, event_type), count in actor_events.items():
        actor_week_events[(window, wk, event_type)] += count
        if week_start(first_seen_actor[actor_id]) == wk:
            actor_week_first[(window, wk, first_event_type[actor_id])].add(actor_id)

    actor_rows = []
    all_keys = set(actor_week_events.keys()) | set(actor_week_first.keys())
    for window, wk, event_type in sorted(all_keys):
        actor_rows.append(
            {
                "window": window,
                "week_start": wk.date().isoformat(),
                "event_type": event_type,
                "events": actor_week_events.get((window, wk, event_type), 0),
                "first_seen_actors_in_window": len(actor_week_first.get((window, wk, event_type), set())),
            }
        )
    actor_panel = pd.DataFrame(actor_rows).sort_values(["window", "week_start", "event_type"])

    summary = pd.DataFrame(
        [
            {
                "window": window_name,
                "files": len(paths),
                "bytes": sum(p.stat().st_size for p in paths),
                "events_filtered": total_events,
                "unique_actors_in_window": len(first_seen_actor),
                "unique_repos_in_window": len(unique_repos),
            }
        ]
    )
    return summary, event_panel, actor_panel, repo_panel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GH Archive entry panels from downloaded hourly files.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--window-name", required=True)
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DIR / "gharchive")
    parser.add_argument("--write-repo-panel", action="store_true")
    parser.add_argument("--hours", default=None, help="Comma-separated UTC hours to keep, e.g. 0,6,12,18.")
    parser.add_argument("--max-files", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    hours = None if args.hours is None else {int(value.strip()) for value in args.hours.split(",") if value.strip()}
    summary, event_panel, actor_panel, repo_panel = build_window_panel(
        args.input_dir,
        args.window_name,
        hours=hours,
        max_files=args.max_files,
        include_repo_panel=args.write_repo_panel,
    )
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    write_csv(summary, out / f"{args.window_name}_summary.csv")
    write_csv(event_panel, out / f"{args.window_name}_event_week.csv")
    write_csv(actor_panel, out / f"{args.window_name}_actor_entry_week.csv")
    if args.write_repo_panel:
        write_csv(repo_panel, out / f"{args.window_name}_repo_event_week.csv")
    logger.info("Wrote GH Archive panels for %s to %s", args.window_name, out)
    logger.info("\n%s", summary.to_string(index=False))


if __name__ == "__main__":
    main()
