"""Prepare question-type mechanism panels from lightweight SEDE exports."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.paths import LOGS_DIR, PROCESSED_DIR, RAW_DIR
from src.utils.io import write_csv
from src.utils.logging_utils import get_logger


RAW_SUBDIR = RAW_DIR / "stackoverflow"
OUTPUT_FILE = PROCESSED_DIR / "stackoverflow_question_type_week_panel_real.csv"

TAG_ALIASES = {
    "selenium-webdriver": "selenium",
    "selenium-chromedriver": "selenium",
    "webdriver": "selenium",
    "chromedriver": "selenium",
}

VERSION_ENV_PAT = re.compile(
    r"\b(?:version|environment|windows|linux|mac|ubuntu|install|installed|"
    r"configuration|dependency|package|build error|compiler|runtime)\b",
    flags=re.IGNORECASE,
)
ADVANCED_PAT = re.compile(
    r"\b(?:architecture|design pattern|scalable|performance|optimization|"
    r"microservice|distributed|best practice)\b",
    flags=re.IGNORECASE,
)
DEBUG_PAT = re.compile(
    r"\b(?:error|exception|traceback|not working|bug|debug|failed|failure|"
    r"crash|segmentation fault)\b",
    flags=re.IGNORECASE,
)
HOWTO_PAT = re.compile(
    r"\b(?:how to|how do i|how can i|what is the way|how should i)\b",
    flags=re.IGNORECASE,
)


def source_files(raw_dir: Path, year: int | None) -> list[Path]:
    if year is None:
        files = sorted(raw_dir.glob("stackoverflow_question_type_raw_*.csv"))
    elif year == 2020:
        files = []
        files += sorted(raw_dir.glob("stackoverflow_question_type_raw_2020_01_w*.csv"))
        files += sorted(raw_dir.glob("stackoverflow_question_type_raw_2020_01_p5.csv"))
        files += sorted(raw_dir.glob("stackoverflow_question_type_raw_2020-*.csv"))
    else:
        files = sorted(raw_dir.glob(f"stackoverflow_question_type_raw_{year}-*.csv"))
    return [
        path
        for path in files
        if path.name != "stackoverflow_question_type_raw_2020_01.csv"
    ]


def classify_questions(df: pd.DataFrame) -> pd.DataFrame:
    title = df["title"].fillna("")
    body_length = pd.to_numeric(df["body_length"], errors="coerce").fillna(0)
    has_code = pd.to_numeric(df["has_code"], errors="coerce").fillna(0).astype(int)

    version_env = title.str.contains(VERSION_ENV_PAT, na=False)
    advanced = title.str.contains(ADVANCED_PAT, na=False)
    debugging = title.str.contains(DEBUG_PAT, na=False)
    howto = title.str.contains(HOWTO_PAT, na=False)
    short_code = (has_code == 1) & (body_length <= 1200)
    long_code = (has_code == 1) & (body_length > 1200)

    conditions = [
        version_env,
        advanced,
        debugging,
        howto,
        short_code,
        long_code,
    ]
    choices = [
        "version_environment_specific",
        "advanced_architecture",
        "debugging_simple",
        "how_to",
        "short_code",
        "long_code",
    ]
    df = df.copy()
    df["question_type"] = np.select(conditions, choices, default="other_conceptual")
    df["substitutable_type"] = np.where(version_env | advanced, 0, 1)
    return df


def load_raw(files: list[Path]) -> pd.DataFrame:
    frames = []
    for path in files:
        frame = pd.read_csv(path)
        frame["source_file"] = path.name
        frames.append(frame)
    if not frames:
        raise FileNotFoundError("No question-type raw files found.")
    df = pd.concat(frames, ignore_index=True)
    df["tag"] = df["tag"].replace(TAG_ALIASES)
    df = df.drop_duplicates(["question_id", "tag"]).reset_index(drop=True)
    df["creation_date"] = pd.to_datetime(df["creation_date"], errors="coerce")
    df["week_start"] = pd.to_datetime(df["week_start"], errors="coerce")
    numeric_cols = [
        "question_id",
        "owner_user_id",
        "body_length",
        "has_code",
        "score",
        "answer_count",
        "has_accepted_answer",
        "is_closed",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def audit_raw(df: pd.DataFrame) -> dict[str, object]:
    return {
        "rows": len(df),
        "date_min": df["creation_date"].min(),
        "date_max": df["creation_date"].max(),
        "tags": df["tag"].nunique(),
        "duplicate_question_tag": int(df.duplicated(["question_id", "tag"]).sum()),
        "source_files": df["source_file"].nunique(),
    }


def build_panel(df: pd.DataFrame) -> pd.DataFrame:
    df = classify_questions(df)
    grouped = (
        df.groupby(["tag", "week_start", "question_type", "substitutable_type"], dropna=False)
        .agg(
            questions=("question_id", "nunique"),
            answers=("answer_count", "sum"),
            accepted_answers=("has_accepted_answer", "sum"),
            avg_score=("score", "mean"),
            closed_questions=("is_closed", "sum"),
            unique_users=("owner_user_id", pd.Series.nunique),
            body_length_mean=("body_length", "mean"),
            code_questions=("has_code", "sum"),
        )
        .reset_index()
    )
    grouped["answer_rate"] = np.where(
        grouped["questions"] > 0, grouped["answers"] / grouped["questions"], np.nan
    )
    grouped["accepted_share"] = np.where(
        grouped["questions"] > 0, grouped["accepted_answers"] / grouped["questions"], np.nan
    )
    grouped["closed_share"] = np.where(
        grouped["questions"] > 0, grouped["closed_questions"] / grouped["questions"], np.nan
    )
    grouped["code_share"] = np.where(
        grouped["questions"] > 0, grouped["code_questions"] / grouped["questions"], np.nan
    )
    return grouped.sort_values(["tag", "week_start", "question_type"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--raw-dir", type=Path, default=RAW_SUBDIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    args = parser.parse_args()

    logger = get_logger(
        "prepare_stackoverflow_question_type_raw",
        LOGS_DIR / "prepare_stackoverflow_question_type_raw.log",
    )
    files = source_files(args.raw_dir, args.year)
    logger.info("Loading %s raw files", len(files))
    raw = load_raw(files)
    audit = audit_raw(raw)
    logger.info("Raw audit: %s", audit)
    if audit["duplicate_question_tag"]:
        raise ValueError(f"Duplicate question-tag rows detected: {audit['duplicate_question_tag']}")
    panel = build_panel(raw)
    write_csv(panel, args.output)
    logger.info("Wrote panel with %s rows to %s", len(panel), args.output)


if __name__ == "__main__":
    main()
