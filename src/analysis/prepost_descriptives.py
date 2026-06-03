"""Tabla descriptiva pre vs post ChatGPT.

Construye varios cortes:
    1. Aggregate pre vs post: total questions, users, answer_rate, etc.
    2. Por substitutable_type.
    3. Por question_type específico (7 categorías).
    4. Por quartile de AI answerability.
    5. Top-10 tags y bottom-10 tags por % Delta.

Pre = 2020-01-01 a 2022-11-29 (153 semanas)
Post = 2022-11-30 a 2024-12-31 (109 semanas)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")


def pct_change(a: float, b: float) -> float:
    return (b - a) / a * 100 if a > 0 else np.nan


def run(panel_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(panel_path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["period"] = np.where(df["week_start"] < CHATGPT_RELEASE, "pre", "post")

    # ===== Aggregate =====
    agg = (
        df.groupby("period")
        .agg(
            n_weeks=("week_start", "nunique"),
            total_questions=("questions", "sum"),
            mean_q_per_week=("questions", lambda x: x.groupby(df.loc[x.index, "week_start"]).sum().mean()),
            total_users=("unique_users", "sum"),
            mean_accepted_share=("accepted_share", "mean"),
            mean_answer_rate=("answer_rate", "mean"),
            mean_closed_share=("closed_share", "mean"),
        )
    )
    print("=== Aggregate pre/post ===")
    print(agg.to_string())
    agg.to_csv(out_dir / "prepost_aggregate.csv")

    # Calcular weekly avg correctly
    weekly = df.groupby(["period", "week_start"]).agg(
        weekly_questions=("questions", "sum"),
        weekly_users=("unique_users", "sum"),
    ).reset_index()
    period_weekly = weekly.groupby("period").agg(
        weeks=("week_start", "nunique"),
        total_q=("weekly_questions", "sum"),
        mean_q_per_week=("weekly_questions", "mean"),
        total_users_sum=("weekly_users", "sum"),
        mean_users_per_week=("weekly_users", "mean"),
    )
    print()
    print("=== Weekly averages pre/post ===")
    print(period_weekly.to_string())
    period_weekly.to_csv(out_dir / "prepost_weekly_averages.csv")
    pre_q = period_weekly.loc["pre", "mean_q_per_week"]
    post_q = period_weekly.loc["post", "mean_q_per_week"]
    print(f"\nDelta questions per week: {pct_change(pre_q, post_q):+.1f}%")

    # ===== Por substitutable_type =====
    by_sub = (
        weekly.merge(
            df[["week_start", "substitutable_type"]].drop_duplicates(),
            on="week_start",
        )
        if False else None  # placeholder, hacemos query directa
    )
    by_sub = (
        df.groupby(["period", "substitutable_type", "week_start"])["questions"].sum()
        .groupby(["period", "substitutable_type"]).mean()
        .unstack("substitutable_type")
        .rename(columns={0: "non_sub_weekly_avg", 1: "sub_weekly_avg"})
    )
    by_sub["delta_sub_pct"] = (
        (by_sub.loc["post", "sub_weekly_avg"] - by_sub.loc["pre", "sub_weekly_avg"])
        / by_sub.loc["pre", "sub_weekly_avg"] * 100
        if "pre" in by_sub.index else np.nan
    )
    print()
    print("=== Sub/non-sub weekly averages ===")
    print(by_sub.to_string())
    by_sub.to_csv(out_dir / "prepost_by_substitutable.csv")
    # Calculate proper deltas
    pre_sub = by_sub.loc["pre"] if "pre" in by_sub.index else None
    post_sub = by_sub.loc["post"] if "post" in by_sub.index else None
    if pre_sub is not None and post_sub is not None:
        print(f"  Delta substitutable: {pct_change(pre_sub['sub_weekly_avg'], post_sub['sub_weekly_avg']):+.1f}%")
        print(f"  Delta non-substitutable: {pct_change(pre_sub['non_sub_weekly_avg'], post_sub['non_sub_weekly_avg']):+.1f}%")

    # ===== Por question_type =====
    by_qt = (
        df.groupby(["period", "question_type", "week_start"])["questions"].sum()
        .groupby(["period", "question_type"]).mean()
        .unstack("period")
        .fillna(0)
    )
    by_qt["delta_pct"] = (by_qt["post"] - by_qt["pre"]) / by_qt["pre"] * 100
    by_qt = by_qt.sort_values("delta_pct")
    print()
    print("=== By question_type ===")
    print(by_qt.to_string())
    by_qt.to_csv(out_dir / "prepost_by_question_type.csv")

    # ===== Por quartile AI =====
    df["ai_q4"] = pd.qcut(df["ai_answerability_zscore"], 4, labels=["Q1_low", "Q2", "Q3", "Q4_high"])
    by_aiq = (
        df.groupby(["period", "ai_q4", "week_start"], observed=True)["questions"].sum()
        .groupby(["period", "ai_q4"], observed=True).mean()
        .unstack("period")
    )
    by_aiq["delta_pct"] = (by_aiq["post"] - by_aiq["pre"]) / by_aiq["pre"] * 100
    print()
    print("=== By AI-answerability quartile ===")
    print(by_aiq.to_string())
    by_aiq.to_csv(out_dir / "prepost_by_ai_quartile.csv")

    # ===== Top/bottom tags por % Delta =====
    by_tag = (
        df.groupby(["tag", "period", "week_start"])["questions"].sum()
        .groupby(["tag", "period"]).mean()
        .unstack("period")
        .fillna(0)
    )
    by_tag["delta_pct"] = (by_tag["post"] - by_tag["pre"]) / by_tag["pre"] * 100
    by_tag = by_tag.merge(
        df[["tag", "ai_answerability_zscore"]].drop_duplicates(),
        on="tag",
    )
    by_tag = by_tag.sort_values("delta_pct")
    print()
    print("=== 10 tags con MAYOR caída relativa ===")
    print(by_tag.head(10).to_string(index=False))
    print()
    print("=== 10 tags con MENOR caída (o crecimiento) ===")
    print(by_tag.tail(10).to_string(index=False))
    by_tag.to_csv(out_dir / "prepost_by_tag.csv", index=False)

    # ===== Correlación tag-level Delta% with AI =====
    valid = by_tag[(by_tag["pre"] > 5) & by_tag["delta_pct"].notna() & by_tag["ai_answerability_zscore"].notna()]
    corr_pearson = valid["delta_pct"].corr(valid["ai_answerability_zscore"])
    corr_spearman = valid["delta_pct"].corr(valid["ai_answerability_zscore"], method="spearman")
    print(f"\n=== Tag-level Delta% vs AI answerability ===")
    print(f"Pearson r = {corr_pearson:+.3f}, Spearman r = {corr_spearman:+.3f}, n={len(valid)}")
    pd.DataFrame([{
        "pearson": corr_pearson, "spearman": corr_spearman, "n": len(valid)
    }]).to_csv(out_dir / "prepost_tag_ai_correlation.csv", index=False)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--panel",
        type=Path,
        default=Path("data/processed/stackoverflow_question_type_master_panel.csv"),
    )
    p.add_argument("--out-dir", type=Path, default=Path("outputs/tables"))
    args = p.parse_args()
    run(args.panel, args.out_dir)
