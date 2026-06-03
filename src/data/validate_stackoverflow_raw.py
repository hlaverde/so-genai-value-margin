import argparse
import hashlib
from pathlib import Path

import pandas as pd

from src.config import EXPECTED_STACKOVERFLOW_FILES
from src.data.clean_stackoverflow import POST_COMPLEXITY_COLUMNS, TAG_WEEK_COLUMNS, USER_TAG_WEEK_COLUMNS
from src.paths import RAW_DIR, TABLES_DIR, ensure_directories
from src.utils.io import write_csv
from src.utils.logging_utils import get_logger


EXPECTED_COLUMNS = {
    EXPECTED_STACKOVERFLOW_FILES["tag_week"]: TAG_WEEK_COLUMNS,
    EXPECTED_STACKOVERFLOW_FILES["user_tag_week"]: USER_TAG_WEEK_COLUMNS,
    EXPECTED_STACKOVERFLOW_FILES["post_complexity"]: POST_COMPLEXITY_COLUMNS,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_csv(path: Path, expected_columns: list[str]) -> dict[str, object]:
    exists = path.exists()
    if not exists:
        return {
            "file": path.name,
            "exists": False,
            "rows": pd.NA,
            "bytes": pd.NA,
            "sha256": pd.NA,
            "missing_columns": ",".join(expected_columns),
            "extra_columns": pd.NA,
        }
    header = pd.read_csv(path, nrows=0)
    missing = sorted(set(expected_columns) - set(header.columns))
    extra = sorted(set(header.columns) - set(expected_columns))
    rows = sum(1 for _ in path.open("r", encoding="utf-8", errors="replace")) - 1
    return {
        "file": path.name,
        "exists": True,
        "rows": max(rows, 0),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "missing_columns": ",".join(missing),
        "extra_columns": ",".join(extra),
    }


def validate_stackoverflow_raw(input_dir: Path, output: Path) -> pd.DataFrame:
    rows = [
        inspect_csv(input_dir / filename, expected_columns)
        for filename, expected_columns in EXPECTED_COLUMNS.items()
    ]
    out = pd.DataFrame(rows)
    write_csv(out, output)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate raw Stack Overflow SEDE CSV exports.")
    parser.add_argument("--input-dir", type=Path, default=RAW_DIR / "stackoverflow")
    parser.add_argument("--output", type=Path, default=TABLES_DIR / "stackoverflow_raw_validation.csv")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    out = validate_stackoverflow_raw(args.input_dir, args.output)
    logger.info("Wrote Stack Overflow raw validation report to %s", args.output)
    logger.info("\n%s", out.to_string(index=False))
    if (out["exists"] == False).any() or out["missing_columns"].fillna("").str.len().gt(0).any():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
