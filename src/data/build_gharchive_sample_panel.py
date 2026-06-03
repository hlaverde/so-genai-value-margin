import argparse
import gzip
from collections import Counter
from pathlib import Path

import pandas as pd

from src.data.build_gharchive_entry_panel import ENTRY_EVENT_TYPES, loads_json
from src.paths import PROCESSED_DIR, RAW_DIR, ensure_directories
from src.utils.io import write_csv
from src.utils.logging_utils import get_logger


def week_start_from_filename(path: Path) -> pd.Timestamp:
    parts = path.name.replace(".json.gz", "").split("-")
    dt = pd.Timestamp(year=int(parts[0]), month=int(parts[1]), day=int(parts[2]))
    return (dt - pd.to_timedelta(dt.weekday(), unit="D")).normalize()


def iter_sample_events(paths: list[Path]):
    for path in sorted(paths):
        wk = week_start_from_filename(path)
        with gzip.open(path, "rb") as handle:
            for line in handle:
                event = loads_json(line)
                event_type = event.get("type")
                if event_type not in ENTRY_EVENT_TYPES:
                    continue
                actor = event.get("actor") or {}
                repo = event.get("repo") or {}
                actor_id = actor.get("id")
                repo_id = repo.get("id")
                if actor_id is None or repo_id is None:
                    continue
                yield {
                    "event_type": event_type,
                    "week_start": wk,
                    "actor_id": int(actor_id),
                    "repo_id": int(repo_id),
                }


def build_sample_panel(input_dir: Path, sample_name: str, file_glob: str = "*.json.gz") -> dict[str, pd.DataFrame]:
    paths = sorted(input_dir.glob(file_glob))
    if not paths:
        raise FileNotFoundError(f"No GH Archive .json.gz files found in {input_dir}")

    first_seen_actor: dict[int, pd.Timestamp] = {}
    first_seen_repo: dict[int, pd.Timestamp] = {}
    event_week = Counter()
    first_actor_week = Counter()
    first_repo_week = Counter()

    total_events = 0
    for event in iter_sample_events(paths):
        total_events += 1
        wk = event["week_start"]
        event_type = event["event_type"]
        actor_id = event["actor_id"]
        repo_id = event["repo_id"]

        event_week[(wk, event_type)] += 1

        if actor_id not in first_seen_actor:
            first_seen_actor[actor_id] = wk
            first_actor_week[(wk, event_type)] += 1
        if repo_id not in first_seen_repo:
            first_seen_repo[repo_id] = wk
            first_repo_week[(wk, event_type)] += 1

    keys = sorted(set(event_week) | set(first_actor_week) | set(first_repo_week))
    panel = pd.DataFrame(
        [
            {
                "sample": sample_name,
                "week_start": wk.date().isoformat(),
                "event_type": event_type,
                "events": event_week.get((wk, event_type), 0),
                "first_seen_actors_in_sample": first_actor_week.get((wk, event_type), 0),
                "first_seen_repos_in_sample": first_repo_week.get((wk, event_type), 0),
            }
            for wk, event_type in keys
        ]
    ).sort_values(["week_start", "event_type"])

    summary = pd.DataFrame(
        [
            {
                "sample": sample_name,
                "files": len(paths),
                "bytes": sum(path.stat().st_size for path in paths),
                "events_filtered": total_events,
                "unique_actors_seen": len(first_seen_actor),
                "unique_repos_seen": len(first_seen_repo),
                "min_file": paths[0].name,
                "max_file": paths[-1].name,
            }
        ]
    )
    return {"summary": summary, "panel": panel}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build cumulative GH Archive sampled panel with first-seen actors/repos.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--sample-name", required=True)
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DIR / "gharchive")
    parser.add_argument("--file-glob", default="*.json.gz")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    outputs = build_sample_panel(args.input_dir, args.sample_name, file_glob=args.file_glob)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / f"{args.sample_name}_sample_summary.csv"
    panel_path = args.output_dir / f"{args.sample_name}_sample_week_event_panel.csv"
    write_csv(outputs["summary"], summary_path)
    write_csv(outputs["panel"], panel_path)
    logger.info("Wrote summary to %s", summary_path)
    logger.info("Wrote panel to %s", panel_path)
    logger.info("\n%s", outputs["summary"].to_string(index=False))


if __name__ == "__main__":
    main()
