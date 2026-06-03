import argparse
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from src.paths import RAW_DIR, ensure_directories
from src.utils.io import write_csv
from src.utils.logging_utils import get_logger


WEEKDAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def parse_weekdays(value: str) -> set[int]:
    out = set()
    for item in value.split(","):
        key = item.strip().lower()
        if key == "":
            continue
        if key.isdigit():
            out.add(int(key))
        elif key in WEEKDAY_MAP:
            out.add(WEEKDAY_MAP[key])
        else:
            raise ValueError(f"Unknown weekday: {item}")
    return out


def build_calendar(start: str, end: str, weekdays: set[int], hour: int) -> pd.DataFrame:
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    rows = []
    current = start_dt
    while current <= end_dt:
        if current.weekday() in weekdays:
            sample_dt = current.replace(hour=hour)
            rows.append(
                {
                    "sample_datetime_utc": sample_dt.strftime("%Y-%m-%d-%H"),
                    "date": current.date().isoformat(),
                    "year": current.year,
                    "weekday": current.weekday(),
                    "hour": hour,
                    "gharchive_url": f"https://data.gharchive.org/{sample_dt:%Y-%m-%d}-{sample_dt.hour}.json.gz",
                    "local_filename": f"{sample_dt:%Y-%m-%d-%H}.json.gz",
                }
            )
        current += timedelta(days=1)
    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a systematic GH Archive sampling calendar.")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD.")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD.")
    parser.add_argument("--weekdays", default="monday,thursday")
    parser.add_argument("--hour", type=int, default=12)
    parser.add_argument("--output", type=Path, default=RAW_DIR / "gharchive" / "sampling_calendar.csv")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    calendar = build_calendar(args.start, args.end, parse_weekdays(args.weekdays), args.hour)
    write_csv(calendar, args.output)
    logger.info("Wrote %s sampled hours to %s", len(calendar), args.output)
    logger.info("\n%s", calendar.groupby("year").size().to_string())


if __name__ == "__main__":
    main()
