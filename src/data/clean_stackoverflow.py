import argparse
from pathlib import Path

import pandas as pd

from src.config import CHATGPT_RELEASE_DATE, EXPECTED_STACKOVERFLOW_FILES
from src.paths import INTERIM_DIR, RAW_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger
from src.utils.validation import assert_no_null_keys, assert_unique_keys, require_columns


TAG_WEEK_COLUMNS = [
    "tag",
    "week_start",
    "questions",
    "answers",
    "accepted_answers",
    "answer_rate",
    "avg_score",
    "closed_questions",
    "unique_users",
]

USER_TAG_WEEK_COLUMNS = [
    "user_id",
    "tag",
    "week_start",
    "reputation_initial",
    "user_age_days",
    "posts",
    "questions",
    "answers",
]

POST_COMPLEXITY_COLUMNS = [
    "post_id",
    "creation_date",
    "tag",
    "body_length",
    "has_code",
    "num_tags",
    "answer_count",
    "has_accepted_answer",
    "score",
]


def clean_tag_week(df: pd.DataFrame) -> pd.DataFrame:
    require_columns(df, TAG_WEEK_COLUMNS, "tag_week")
    out = df[TAG_WEEK_COLUMNS].copy()
    out["tag"] = out["tag"].astype(str).str.strip().str.lower()
    out["week_start"] = pd.to_datetime(out["week_start"]).dt.date
    numeric_cols = [c for c in TAG_WEEK_COLUMNS if c not in {"tag", "week_start"}]
    out[numeric_cols] = out[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    out["post_chatgpt"] = pd.to_datetime(out["week_start"]) >= pd.Timestamp(CHATGPT_RELEASE_DATE)
    assert_no_null_keys(out, ["tag", "week_start"], "tag_week")
    assert_unique_keys(out, ["tag", "week_start"], "tag_week")
    return out.sort_values(["tag", "week_start"])


def clean_user_tag_week(df: pd.DataFrame) -> pd.DataFrame:
    require_columns(df, USER_TAG_WEEK_COLUMNS, "user_tag_week")
    out = df[USER_TAG_WEEK_COLUMNS].copy()
    out["user_id"] = pd.to_numeric(out["user_id"], errors="coerce").astype("Int64")
    out["tag"] = out["tag"].astype(str).str.strip().str.lower()
    out["week_start"] = pd.to_datetime(out["week_start"]).dt.date
    numeric_cols = [c for c in USER_TAG_WEEK_COLUMNS if c not in {"user_id", "tag", "week_start"}]
    out[numeric_cols] = out[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    out["post_chatgpt"] = pd.to_datetime(out["week_start"]) >= pd.Timestamp(CHATGPT_RELEASE_DATE)
    assert_no_null_keys(out, ["user_id", "tag", "week_start"], "user_tag_week")
    assert_unique_keys(out, ["user_id", "tag", "week_start"], "user_tag_week")
    return out.sort_values(["user_id", "tag", "week_start"])


def clean_post_complexity(df: pd.DataFrame) -> pd.DataFrame:
    require_columns(df, POST_COMPLEXITY_COLUMNS, "post_complexity")
    keep = POST_COMPLEXITY_COLUMNS + [c for c in ["title", "body"] if c in df.columns]
    out = df[keep].copy()
    out["post_id"] = pd.to_numeric(out["post_id"], errors="coerce").astype("Int64")
    out["tag"] = out["tag"].astype(str).str.strip().str.lower()
    out["creation_date"] = pd.to_datetime(out["creation_date"])
    numeric_cols = ["body_length", "has_code", "num_tags", "answer_count", "has_accepted_answer", "score"]
    out[numeric_cols] = out[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    out["post_chatgpt"] = out["creation_date"] >= pd.Timestamp(CHATGPT_RELEASE_DATE)
    assert_no_null_keys(out, ["post_id", "tag"], "post_complexity")
    return out.sort_values(["creation_date", "post_id", "tag"])


def clean_stackoverflow(input_dir: Path, output_dir: Path) -> dict[str, Path]:
    ensure_directories()
    logger = get_logger(__name__)
    output_dir.mkdir(parents=True, exist_ok=True)

    tag_week = clean_tag_week(read_csv(input_dir / EXPECTED_STACKOVERFLOW_FILES["tag_week"]))
    user_tag_week = clean_user_tag_week(read_csv(input_dir / EXPECTED_STACKOVERFLOW_FILES["user_tag_week"]))
    post_complexity = clean_post_complexity(read_csv(input_dir / EXPECTED_STACKOVERFLOW_FILES["post_complexity"]))

    outputs = {
        "tag_week": output_dir / "tag_week_clean.csv",
        "user_tag_week": output_dir / "user_tag_week_clean.csv",
        "post_complexity": output_dir / "post_complexity_clean.csv",
    }
    write_csv(tag_week, outputs["tag_week"])
    write_csv(user_tag_week, outputs["user_tag_week"])
    write_csv(post_complexity, outputs["post_complexity"])
    logger.info("Wrote cleaned Stack Overflow files to %s", output_dir)
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean manually downloaded Stack Overflow SEDE CSV files.")
    parser.add_argument("--input-dir", type=Path, default=RAW_DIR / "stackoverflow")
    parser.add_argument("--output-dir", type=Path, default=INTERIM_DIR / "stackoverflow")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    clean_stackoverflow(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()
