"""Figuras descriptivas macro del paper.

Genera:
    1. Time series semanal de questions agregadas (todos los tags top-100).
    2. Decomposed por substitutable vs non-substitutable.
    3. Stack chart por question_type (7 categorías).
    4. Time series por quartile de AI answerability.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")
PALETTE_SUB = {0: "#4C72B0", 1: "#DD8452"}
QTYPE_ORDER = [
    "long_code", "short_code", "how_to", "debugging_simple",
    "other_conceptual", "version_environment_specific", "advanced_architecture",
]


def main(panel_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(panel_path)
    df["week_start"] = pd.to_datetime(df["week_start"])

    # =============================
    # Fig 1: Total semanal
    # =============================
    total = df.groupby("week_start")["questions"].sum().reset_index()
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(total["week_start"], total["questions"], color="black", linewidth=1.2)
    ax.axvline(CHATGPT_RELEASE, color="firebrick", linestyle="--", alpha=0.7, label="ChatGPT release")
    ax.set_ylabel("Questions per week (top-100 tags)")
    ax.set_xlabel("")
    ax.set_title("Stack Overflow questions — top-100 tags, 2020–2024")
    ax.legend(loc="upper right")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    fig.savefig(out_dir / "macro_total_weekly.png", dpi=160)
    plt.close(fig)

    # =============================
    # Fig 2: Substitutable vs non-substitutable
    # =============================
    by_sub = (
        df.groupby(["week_start", "substitutable_type"])["questions"]
        .sum()
        .unstack("substitutable_type")
        .rename(columns={0: "non_substitutable", 1: "substitutable"})
    )
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(by_sub.index, by_sub["substitutable"], color=PALETTE_SUB[1], label="Substitutable", linewidth=1.5)
    ax.plot(by_sub.index, by_sub["non_substitutable"], color=PALETTE_SUB[0], label="Non-substitutable", linewidth=1.5)
    ax.axvline(CHATGPT_RELEASE, color="firebrick", linestyle="--", alpha=0.7, label="ChatGPT release")
    ax.set_ylabel("Questions per week")
    ax.set_yscale("log")
    ax.set_title("Substitutable vs non-substitutable question types (log scale)")
    ax.legend(loc="upper right")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    fig.savefig(out_dir / "macro_substitutable_vs_not_log.png", dpi=160)
    plt.close(fig)

    # =============================
    # Fig 3: Stack por question_type
    # =============================
    by_q = (
        df.groupby(["week_start", "question_type"])["questions"]
        .sum()
        .unstack("question_type")
        .reindex(columns=QTYPE_ORDER)
        .fillna(0)
    )
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.stackplot(
        by_q.index, by_q.T.values, labels=by_q.columns,
        alpha=0.9,
    )
    ax.axvline(CHATGPT_RELEASE, color="black", linestyle="--", alpha=0.8)
    ax.set_ylabel("Questions per week (stacked)")
    ax.set_title("Question composition by type, 2020–2024")
    ax.legend(loc="upper right", fontsize=7)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    fig.savefig(out_dir / "macro_stacked_question_type.png", dpi=160)
    plt.close(fig)

    # =============================
    # Fig 4: Quartiles de AI answerability
    # =============================
    df["ai_q4"] = pd.qcut(df["ai_answerability_zscore"], 4, labels=["Q1 (low)", "Q2", "Q3", "Q4 (high)"])
    by_aiq = (
        df.groupby(["week_start", "ai_q4"], observed=True)["questions"]
        .sum()
        .unstack("ai_q4")
    )
    # Normalizar a 100 en la primera semana
    norm_base = by_aiq.iloc[:13].mean()  # promedio de las primeras 13 semanas
    by_aiq_n = by_aiq.div(norm_base, axis=1) * 100
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for col in by_aiq_n.columns:
        ax.plot(by_aiq_n.index, by_aiq_n[col], label=col, linewidth=1.3)
    ax.axvline(CHATGPT_RELEASE, color="firebrick", linestyle="--", alpha=0.7, label="ChatGPT release")
    ax.axhline(100, color="grey", linestyle=":", alpha=0.5)
    ax.set_ylabel("Questions per week (Q1 2020 = 100)")
    ax.set_title("Question volume by AI-answerability quartile, indexed to early 2020")
    ax.legend(loc="lower left", fontsize=8, ncol=4)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    fig.savefig(out_dir / "macro_quartiles_ai_indexed.png", dpi=160)
    plt.close(fig)

    print(f"saved figures to {out_dir}")
    print("  macro_total_weekly.png")
    print("  macro_substitutable_vs_not_log.png")
    print("  macro_stacked_question_type.png")
    print("  macro_quartiles_ai_indexed.png")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--panel",
        type=Path,
        default=Path("data/processed/stackoverflow_question_type_master_panel.csv"),
    )
    p.add_argument("--out-dir", type=Path, default=Path("outputs/figures"))
    args = p.parse_args()
    main(args.panel, args.out_dir)
