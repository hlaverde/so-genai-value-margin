import argparse
import gzip
import shutil
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from src.paths import RAW_DIR, ensure_directories
from src.utils.logging_utils import get_logger


def iter_hours(start: datetime, end: datetime):
    current = start
    while current <= end:
        yield current
        current += timedelta(hours=1)


def gharchive_url(hour: datetime) -> str:
    return f"https://data.gharchive.org/{hour:%Y-%m-%d}-{hour.hour}.json.gz"


def download_hour(hour: datetime, output_dir: Path, overwrite: bool = False) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{hour:%Y-%m-%d-%H}.json.gz"
    if path.exists() and not overwrite:
        return path
    request = urllib.request.Request(
        gharchive_url(hour),
        headers={
            "User-Agent": "ai-knowledge-commons-shock/0.1 academic reproducibility script",
            "Accept": "application/gzip, application/octet-stream, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        with path.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    with gzip.open(path, "rb") as handle:
        handle.peek(1)
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Selectively download GH Archive hourly files by HTTP.")
    parser.add_argument("--start", required=True, help="UTC start hour, format YYYY-MM-DD-HH.")
    parser.add_argument("--end", required=True, help="UTC end hour, format YYYY-MM-DD-HH.")
    parser.add_argument("--output-dir", type=Path, default=RAW_DIR / "gharchive")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--hours", default=None, help="Optional comma-separated UTC hours to download, e.g. 12 or 0,6,12,18.")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    start = datetime.strptime(args.start, "%Y-%m-%d-%H")
    end = datetime.strptime(args.end, "%Y-%m-%d-%H")
    if end < start:
        raise ValueError("--end must be after --start")
    selected_hours = None if args.hours is None else {int(value.strip()) for value in args.hours.split(",") if value.strip()}
    hours_to_download = [
        hour for hour in iter_hours(start, end)
        if selected_hours is None or hour.hour in selected_hours
    ]
    logger.info("Downloading %s GH Archive hourly files", len(hours_to_download))
    for hour in hours_to_download:
        path = download_hour(hour, args.output_dir, overwrite=args.overwrite)
        logger.info("Ready: %s", path)


if __name__ == "__main__":
    main()
