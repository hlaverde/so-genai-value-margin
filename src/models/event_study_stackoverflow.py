import argparse
from pathlib import Path

import pandas as pd

from src.config import CHATGPT_RELEASE_DATE
from src.paths import PROCESSED_DIR, TABLES_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


def add_relative_week(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["week_start"] = pd.to_datetime(out["week_start"])
    out["relative_week"] = ((out["week_start"] - pd.Timestamp(CHATGPT_RELEASE_DATE)).dt.days // 7).astype(int)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare relative-week event-study design data.")
    parser.add_argument("--input", type=Path, default=PROCESSED_DIR / "stackoverflow_tag_week_panel.csv")
    parser.add_argument("--output", type=Path, default=TABLES_DIR / "event_study_design.csv")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    out = add_relative_week(read_csv(args.input))
    write_csv(out, args.output)
    logger.info("Wrote event-study design data to %s", args.output)


if __name__ == "__main__":
    main()
