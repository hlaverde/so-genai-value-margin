import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import CHATGPT_RELEASE_DATE
from src.paths import PROCESSED_DIR, RAW_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


DEFAULT_FILES = [
    "stackoverflow_fractional_tag_week_2018_2019.csv",
    "stackoverflow_fractional_tag_week_2020_2021.csv",
    "stackoverflow_fractional_tag_week_2022_2023.csv",
    "stackoverflow_fractional_tag_week_2024_2026.csv",
]


def load_fractional_files(input_dir: Path, filenames: list[str]) -> pd.DataFrame:
    frames = []
    for filename in filenames:
        path = input_dir / filename
        df = read_csv(path)
        df["source_file"] = filename
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["week_start"] = pd.to_datetime(out["week_start"])
    # Adjacent date windows can overlap at boundary weeks. Keep one row per tag-week
    # by summing fractional count outcomes and averaging rates/scores using questions
    # as weights where possible.
    count_cols = ["questions", "answers", "accepted_answers", "closed_questions"]
    grouped_rows = []
    for (tag, week), g in out.groupby(["tag", "week_start"]):
        q = g["questions"].sum()
        row = {
            "tag": tag,
            "week_start": week,
            "questions": q,
            "answers": g["answers"].sum(),
            "accepted_answers": g["accepted_answers"].sum(),
            "closed_questions": g["closed_questions"].sum(),
            "unique_users": g["unique_users"].sum(),
            "source_files": ";".join(sorted(g["source_file"].unique())),
        }
        row["answer_rate"] = row["answers"] / q if q > 0 else 0
        row["avg_score"] = np.average(g["avg_score"], weights=g["questions"]) if q > 0 else g["avg_score"].mean()
        grouped_rows.append(row)
    return pd.DataFrame(grouped_rows).sort_values(["tag", "week_start"]).reset_index(drop=True)


def attach_ai_indices(panel: pd.DataFrame, ai_path: Path) -> pd.DataFrame:
    ai = read_csv(ai_path)
    out = panel.merge(ai[["tag", "ai_answerability_zscore", "ai_answerability_pca", "ai_answerability_quantile", "ai_answerability_structural"]], on="tag", how="left")
    out["post_chatgpt"] = out["week_start"] >= pd.Timestamp(CHATGPT_RELEASE_DATE)
    out["log_questions"] = np.log1p(out["questions"])
    out["log_answers"] = np.log1p(out["answers"])
    out["log_unique_users"] = np.log1p(out["unique_users"])
    out["log_accepted_answers"] = np.log1p(out["accepted_answers"])
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare fractional-count Stack Overflow tag-week panel.")
    parser.add_argument("--input-dir", type=Path, default=RAW_DIR / "stackoverflow")
    parser.add_argument("--ai", type=Path, default=PROCESSED_DIR / "ai_answerability_real.csv")
    parser.add_argument("--output", type=Path, default=PROCESSED_DIR / "stackoverflow_fractional_tag_week_panel_real.csv")
    parser.add_argument("--files", nargs="*", default=DEFAULT_FILES)
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    panel = load_fractional_files(args.input_dir, args.files)
    panel = attach_ai_indices(panel, args.ai)
    write_csv(panel, args.output)
    logger.info("Wrote fractional panel to %s", args.output)
    logger.info("Rows=%s tags=%s min_week=%s max_week=%s", len(panel), panel["tag"].nunique(), panel["week_start"].min().date(), panel["week_start"].max().date())
    logger.info("Missing AI rows=%s", panel["ai_answerability_zscore"].isna().sum())


if __name__ == "__main__":
    main()
