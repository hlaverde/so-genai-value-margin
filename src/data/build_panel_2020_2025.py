"""Append the full 2025 question-type panel to the existing 2020-2024 master panel."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.prepare_stackoverflow_question_type_raw import classify_questions  # noqa: E402
from src.paths import PROCESSED_DIR  # noqa: E402

CHATGPT_RELEASE = pd.Timestamp("2022-11-30")
ANSWERABILITY_COLS = [
    "ai_answerability_zscore",
    "ai_answerability_pca",
    "ai_answerability_quantile",
    "ai_answerability_structural",
]


def aggregate_2025(clean_path: Path) -> pd.DataFrame:
    raw = pd.read_csv(clean_path)
    if raw.empty:
        raise SystemExit(f"No clean 2025 rows found in {clean_path}")
    raw["tag"] = raw["tag_consulted"]
    raw["week_start"] = pd.to_datetime(raw["week_start"])
    raw["creation_date"] = pd.to_datetime(raw["creation_date"])
    for col in ["question_id", "owner_user_id", "body_length", "has_code", "score", "answer_count", "has_accepted_answer", "is_closed"]:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    classified = classify_questions(raw)
    grouped = classified.groupby(["tag", "week_start", "question_type", "substitutable_type"], dropna=False).agg(
        questions=("question_id", "nunique"),
        answers=("answer_count", "sum"),
        accepted_answers=("has_accepted_answer", "sum"),
        avg_score=("score", "mean"),
        closed_questions=("is_closed", "sum"),
        unique_users=("owner_user_id", pd.Series.nunique),
        body_length_mean=("body_length", "mean"),
        code_questions=("has_code", "sum"),
    ).reset_index()
    grouped["answer_rate"] = np.where(grouped["questions"] > 0, grouped["answers"] / grouped["questions"], np.nan)
    grouped["accepted_share"] = np.where(grouped["questions"] > 0, grouped["accepted_answers"] / grouped["questions"], np.nan)
    grouped["closed_share"] = np.where(grouped["questions"] > 0, grouped["closed_questions"] / grouped["questions"], np.nan)
    grouped["code_share"] = np.where(grouped["questions"] > 0, grouped["code_questions"] / grouped["questions"], np.nan)
    grouped["year"] = grouped["week_start"].dt.year
    return grouped


def add_design_columns(panel: pd.DataFrame, answerability_path: Path) -> pd.DataFrame:
    panel = panel.copy()
    panel["week_start"] = pd.to_datetime(panel["week_start"])
    base_cols = [c for c in panel.columns if not c.startswith("ai_answerability_")]
    panel = panel[base_cols]
    ans = pd.read_csv(answerability_path)
    keep = ["tag"] + ANSWERABILITY_COLS + [
        "questions_pre",
        "accepted_answer_rate_pre",
        "short_code_share_pre",
        "how_to_share_pre",
    ]
    if "embedding_answerability" in ans.columns:
        keep.append("embedding_answerability")
    panel = panel.merge(ans[keep], on="tag", how="left", validate="many_to_one")
    panel["post_chatgpt"] = (panel["week_start"] >= CHATGPT_RELEASE).astype(int)
    panel["post_chatgpt_bool"] = panel["week_start"] >= CHATGPT_RELEASE
    panel["post"] = panel["post_chatgpt"]
    panel["week"] = panel["week_start"]
    panel["substitutable"] = panel["substitutable_type"]
    panel["n_questions"] = panel["questions"]
    panel["n_unique_users"] = panel["unique_users"]
    panel["mean_score"] = panel["avg_score"]
    panel["log_questions_p1"] = np.log1p(panel["questions"])
    panel["log_questions"] = np.where(panel["questions"] > 0, np.log(panel["questions"]), np.nan)
    panel["log_unique_users_p1"] = np.log1p(panel["unique_users"])
    panel["accepted_per_q"] = np.where(panel["questions"] > 0, panel["accepted_answers"] / panel["questions"], np.nan)
    min_week = panel["week_start"].min()
    panel["weeks_from_start"] = ((panel["week_start"] - min_week).dt.days // 7).astype(int)
    panel["weeks_from_chatgpt"] = ((panel["week_start"] - CHATGPT_RELEASE).dt.days // 7).astype(int)
    panel["tag_qtype"] = panel["tag"].astype(str) + "::" + panel["question_type"].astype(str)
    dup = panel.duplicated(["tag", "week_start", "question_type"]).sum()
    if dup:
        raise ValueError(f"Duplicate tag-week-question_type cells: {dup}")
    return panel.sort_values(["tag", "week_start", "question_type"]).reset_index(drop=True)


def consolidate_cells(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    panel["week_start"] = pd.to_datetime(panel["week_start"])
    group_cols = ["tag", "week_start", "question_type", "substitutable_type"]
    agg_spec = {
        "questions": "sum",
        "answers": "sum",
        "accepted_answers": "sum",
        "closed_questions": "sum",
        "code_questions": "sum",
        "unique_users": "sum",
        "avg_score": "mean",
        "body_length_mean": "mean",
    }
    available = {col: fn for col, fn in agg_spec.items() if col in panel.columns}
    out = panel.groupby(group_cols, as_index=False, dropna=False).agg(available)
    out["answer_rate"] = np.where(out["questions"] > 0, out["answers"] / out["questions"], np.nan)
    out["accepted_share"] = np.where(out["questions"] > 0, out["accepted_answers"] / out["questions"], np.nan)
    out["closed_share"] = np.where(out["questions"] > 0, out["closed_questions"] / out["questions"], np.nan)
    out["code_share"] = np.where(out["questions"] > 0, out["code_questions"] / out["questions"], np.nan)
    out["year"] = out["week_start"].dt.year
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-2024", type=Path, default=PROCESSED_DIR / "stackoverflow_question_type_master_panel.csv")
    parser.add_argument("--clean-2025", type=Path, default=PROCESSED_DIR / "stackoverflow_2025_clean_question_tag.csv")
    parser.add_argument("--answerability", type=Path, default=PROCESSED_DIR / "ai_answerability_real.csv")
    parser.add_argument("--output", type=Path, default=PROCESSED_DIR / "panel_tag_week_question_type_2020_2025.csv")
    args = parser.parse_args()
    master = pd.read_csv(args.master_2024)
    master["week_start"] = pd.to_datetime(master["week_start"])
    master = master[master["week_start"].dt.year <= 2024].copy()
    p25 = aggregate_2025(args.clean_2025)
    combined = pd.concat([master, p25], ignore_index=True, sort=False)
    combined = consolidate_cells(combined)
    out = add_design_columns(combined, args.answerability)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    print(f"panel rows={len(out):,}, tags={out['tag'].nunique()}, weeks={out['week_start'].nunique()}, qtypes={out['question_type'].nunique()}")
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
