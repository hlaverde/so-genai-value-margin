import argparse
from pathlib import Path

import pandas as pd

from src.config import CHATGPT_RELEASE_DATE
from src.paths import EXTERNAL_DIR, PROCESSED_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger
from src.utils.validation import require_columns


def build_so_dependence(tag_week: pd.DataFrame, language_tag_map: pd.DataFrame) -> pd.DataFrame:
    require_columns(tag_week, ["tag", "week_start", "questions"], "tag_week_panel")
    require_columns(language_tag_map, ["language", "tag", "weight"], "language_tag_map")
    df = tag_week.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    pre = df[df["week_start"] < pd.Timestamp(CHATGPT_RELEASE_DATE)].copy()
    mapped = pre.merge(language_tag_map, on="tag", how="inner")
    mapped["weighted_questions"] = mapped["questions"] * mapped["weight"]
    out = (
        mapped.groupby("language", as_index=False)
        .agg(
            so_questions_pre=("weighted_questions", "sum"),
            mapped_tags=("tag", "nunique"),
            active_weeks=("week_start", "nunique"),
        )
        .sort_values("so_questions_pre", ascending=False)
    )
    out["so_dependence_share"] = out["so_questions_pre"] / out["so_questions_pre"].sum()
    out["so_dependence_log"] = (out["so_questions_pre"] + 1).apply("log")
    out["so_dependence_rank"] = out["so_questions_pre"].rank(pct=True)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build language-level Stack Overflow dependence from tag-week panel.")
    parser.add_argument("--tag-week", type=Path, default=PROCESSED_DIR / "stackoverflow_tag_week_panel_real.csv")
    parser.add_argument("--language-tag-map", type=Path, default=EXTERNAL_DIR / "language_tag_map.csv")
    parser.add_argument("--output", type=Path, default=PROCESSED_DIR / "so_dependence_language.csv")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    out = build_so_dependence(read_csv(args.tag_week), read_csv(args.language_tag_map))
    write_csv(out, args.output)
    logger.info("Wrote language SO dependence to %s", args.output)
    logger.info("\n%s", out.to_string(index=False))


if __name__ == "__main__":
    main()
