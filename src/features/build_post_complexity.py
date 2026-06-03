import argparse
from pathlib import Path

import pandas as pd

from src.config import DEFAULT_SHORT_BODY_CHARS
from src.paths import INTERIM_DIR, PROCESSED_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger
from src.utils.validation import require_columns


HOW_TO_PATTERNS = (
    "how to",
    "how do i",
    "how can i",
    "why does",
    "what is",
    "error",
    "fix",
)


def build_post_complexity(df: pd.DataFrame, short_body_chars: int = DEFAULT_SHORT_BODY_CHARS) -> pd.DataFrame:
    require_columns(
        df,
        ["post_id", "creation_date", "tag", "body_length", "has_code", "num_tags", "answer_count", "has_accepted_answer", "score"],
        "post_complexity_clean",
    )
    out = df.copy()
    out["creation_date"] = pd.to_datetime(out["creation_date"])
    for col in ["body_length", "has_code", "num_tags", "answer_count", "has_accepted_answer", "score"]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    text = ""
    if "title" in out.columns:
        text = out["title"].fillna("").astype(str).str.lower()
    if "body" in out.columns:
        body_text = out["body"].fillna("").astype(str).str.lower()
        text = text + " " + body_text if not isinstance(text, str) else body_text

    if isinstance(text, str):
        out["how_to_question"] = 0
    else:
        out["how_to_question"] = text.apply(lambda value: int(any(pattern in value for pattern in HOW_TO_PATTERNS)))

    out["short_code_question"] = ((out["has_code"] == 1) & (out["body_length"] <= short_body_chars)).astype(int)
    out["complexity_score_simple"] = (
        out["body_length"].rank(pct=True)
        + out["num_tags"].rank(pct=True)
        + out["answer_count"].rank(pct=True)
        - out["short_code_question"].rank(pct=True)
    )
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build simple Stack Overflow post-complexity features.")
    parser.add_argument("--input", type=Path, default=INTERIM_DIR / "stackoverflow" / "post_complexity_clean.csv")
    parser.add_argument("--output", type=Path, default=PROCESSED_DIR / "post_complexity_features.csv")
    parser.add_argument("--short-body-chars", type=int, default=DEFAULT_SHORT_BODY_CHARS)
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    out = build_post_complexity(read_csv(args.input), short_body_chars=args.short_body_chars)
    write_csv(out, args.output)
    logger.info("Wrote post complexity features to %s", args.output)


if __name__ == "__main__":
    main()
