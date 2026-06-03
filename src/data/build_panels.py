import argparse
from pathlib import Path

import pandas as pd

from src.paths import INTERIM_DIR, PROCESSED_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


def build_stackoverflow_analysis_panel(tag_week: pd.DataFrame, ai_answerability: pd.DataFrame) -> pd.DataFrame:
    out = tag_week.merge(
        ai_answerability[
            [
                "tag",
                "ai_answerability_zscore",
                "ai_answerability_pca",
                "ai_answerability_quantile",
                "ai_answerability_structural",
            ]
        ],
        on="tag",
        how="left",
    )
    out["week_start"] = pd.to_datetime(out["week_start"])
    return out.sort_values(["tag", "week_start"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build analysis panels from cleaned and feature data.")
    parser.add_argument("--tag-week", type=Path, default=INTERIM_DIR / "stackoverflow" / "tag_week_clean.csv")
    parser.add_argument("--ai-answerability", type=Path, default=PROCESSED_DIR / "ai_answerability.csv")
    parser.add_argument("--output", type=Path, default=PROCESSED_DIR / "stackoverflow_tag_week_panel.csv")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    out = build_stackoverflow_analysis_panel(read_csv(args.tag_week), read_csv(args.ai_answerability))
    write_csv(out, args.output)
    logger.info("Wrote Stack Overflow analysis panel to %s", args.output)


if __name__ == "__main__":
    main()
