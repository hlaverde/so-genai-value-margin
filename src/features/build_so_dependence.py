import argparse
from pathlib import Path

import pandas as pd

from src.paths import PROCESSED_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


def build_so_dependence(tag_language_map: pd.DataFrame, tag_week: pd.DataFrame) -> pd.DataFrame:
    merged = tag_week.merge(tag_language_map, on="tag", how="inner")
    out = (
        merged.groupby("language", as_index=False)
        .agg(pre_so_questions=("questions", "sum"), active_tags=("tag", "nunique"))
        .sort_values("language")
    )
    out["so_dependence"] = out["pre_so_questions"] / out["pre_so_questions"].sum()
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build language-level Stack Overflow dependence from a tag-language map.")
    parser.add_argument("--tag-language-map", type=Path, required=True)
    parser.add_argument("--tag-week", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=PROCESSED_DIR / "so_dependence.csv")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    out = build_so_dependence(read_csv(args.tag_language_map), read_csv(args.tag_week))
    write_csv(out, args.output)
    logger.info("Wrote Stack Overflow dependence measures to %s", args.output)


if __name__ == "__main__":
    main()
