import argparse
from pathlib import Path

import pandas as pd

from src.config import DEFAULT_LOW_REPUTATION_THRESHOLD, DEFAULT_NEW_USER_DAYS
from src.paths import INTERIM_DIR, PROCESSED_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger
from src.utils.validation import require_columns


def build_user_status(
    df: pd.DataFrame,
    new_user_days: int = DEFAULT_NEW_USER_DAYS,
    low_reputation_threshold: int = DEFAULT_LOW_REPUTATION_THRESHOLD,
) -> pd.DataFrame:
    require_columns(
        df,
        ["user_id", "tag", "week_start", "reputation_initial", "user_age_days", "posts", "questions", "answers"],
        "user_tag_week_clean",
    )
    out = df.copy()
    out["week_start"] = pd.to_datetime(out["week_start"]).dt.date
    for col in ["reputation_initial", "user_age_days", "posts", "questions", "answers"]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    out["new_user"] = (out["user_age_days"] <= new_user_days).astype(int)
    out["low_reputation_user"] = (out["reputation_initial"] <= low_reputation_threshold).astype(int)
    out["entry_level_user"] = ((out["new_user"] == 1) | (out["low_reputation_user"] == 1)).astype(int)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build user status indicators for Stack Overflow user-tag-week data.")
    parser.add_argument("--input", type=Path, default=INTERIM_DIR / "stackoverflow" / "user_tag_week_clean.csv")
    parser.add_argument("--output", type=Path, default=PROCESSED_DIR / "user_status.csv")
    parser.add_argument("--new-user-days", type=int, default=DEFAULT_NEW_USER_DAYS)
    parser.add_argument("--low-reputation-threshold", type=int, default=DEFAULT_LOW_REPUTATION_THRESHOLD)
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    out = build_user_status(
        read_csv(args.input),
        new_user_days=args.new_user_days,
        low_reputation_threshold=args.low_reputation_threshold,
    )
    write_csv(out, args.output)
    logger.info("Wrote user status features to %s", args.output)


if __name__ == "__main__":
    main()
