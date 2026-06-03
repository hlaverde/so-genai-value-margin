import argparse
import gzip
import shutil
import urllib.request
from pathlib import Path

import pandas as pd

from src.paths import RAW_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


def download_url(url: str, path: Path, overwrite: bool = False) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return "exists"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ai-knowledge-commons-shock/0.1 academic reproducibility script",
            "Accept": "application/gzip, application/octet-stream, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        with path.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    with gzip.open(path, "rb") as handle:
        handle.peek(1)
    return "downloaded"


def download_calendar(calendar_path: Path, output_dir: Path, year: int | None, overwrite: bool = False) -> pd.DataFrame:
    calendar = read_csv(calendar_path)
    if year is not None:
        calendar = calendar[calendar["year"] == year].copy()
    rows = []
    for _, row in calendar.iterrows():
        path = output_dir / str(row["local_filename"])
        try:
            status = download_url(str(row["gharchive_url"]), path, overwrite=overwrite)
            error = ""
        except Exception as exc:
            status = "error"
            error = repr(exc)
        rows.append(
            {
                "sample_datetime_utc": row["sample_datetime_utc"],
                "year": row["year"],
                "url": row["gharchive_url"],
                "path": str(path),
                "status": status,
                "bytes": path.stat().st_size if path.exists() else 0,
                "error": error,
            }
        )
    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download GH Archive files from a sampling calendar.")
    parser.add_argument("--calendar", type=Path, default=RAW_DIR / "gharchive" / "sampling_calendar.csv")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--log-output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    log_output = args.log_output or (args.output_dir / "download_log.csv")
    report = download_calendar(args.calendar, args.output_dir, args.year, overwrite=args.overwrite)
    write_csv(report, log_output)
    logger.info("Wrote download log to %s", log_output)
    logger.info("\n%s", report.groupby("status").size().to_string())
    logger.info("Downloaded/existing GB: %.2f", report["bytes"].sum() / 1024**3)
    if (report["status"] == "error").any():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
