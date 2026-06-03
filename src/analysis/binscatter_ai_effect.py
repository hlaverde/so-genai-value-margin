"""Bin-scatter visualizando el gradiente lineal en AI answerability.

Para cada tag, calculamos Δlog(Q) = log(Q_post) - log(Q_pre) (sumando
todas las question_types). Lo plotamos contra el score de answerability.
La pendiente de este scatter es la versión "reducida" del efecto AI×Post
que aparece en el DDD principal.

Salida:
    outputs/figures/binscatter_ai_effect.png
    outputs/tables/binscatter_ai_effect.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")


def build_tag_data(panel_path: Path, ai_col: str) -> pd.DataFrame:
    df = pd.read_csv(panel_path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["period"] = np.where(df["week_start"] < CHATGPT_RELEASE, "pre", "post")

    weekly_tag = (
        df.groupby(["tag", "period", "week_start"])["questions"].sum().reset_index()
    )
    by_tag = weekly_tag.groupby(["tag", "period"])["questions"].mean().unstack("period")
    by_tag["log_pre"] = np.log1p(by_tag["pre"])
    by_tag["log_post"] = np.log1p(by_tag["post"])
    by_tag["dlog"] = by_tag["log_post"] - by_tag["log_pre"]

    ai = df[["tag", ai_col]].drop_duplicates()
    by_tag = by_tag.merge(ai, on="tag")
    return by_tag.reset_index(drop=True)


def main(panel_path: Path, out_csv: Path, out_fig: Path, ai_col: str, n_bins: int = 20) -> None:
    df = build_tag_data(panel_path, ai_col)
    df = df.dropna(subset=["dlog", ai_col])

    # Linear regression line
    slope, intercept, r, p, _ = stats.linregress(df[ai_col], df["dlog"])
    print(f"Linear fit: slope = {slope:+.4f}, intercept = {intercept:+.4f}, r = {r:+.3f}, p = {p:.3g}, n={len(df)}")

    # Quantile bins
    df["ai_bin"] = pd.qcut(df[ai_col], n_bins, duplicates="drop")
    bins = df.groupby("ai_bin", observed=True).agg(
        ai_mean=(ai_col, "mean"),
        dlog_mean=("dlog", "mean"),
        dlog_se=("dlog", lambda x: x.std() / np.sqrt(len(x))),
        n_tags=("tag", "count"),
    ).reset_index(drop=True)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    bins.to_csv(out_csv, index=False)
    print(f"saved {out_csv}")

    # Plot
    fig, ax = plt.subplots(figsize=(8, 5.5))
    # Raw scatter
    ax.scatter(df[ai_col], df["dlog"], s=18, alpha=0.35, color="grey", label="Tags (raw)")
    # Bins with error bars
    ax.errorbar(bins["ai_mean"], bins["dlog_mean"],
                yerr=1.96 * bins["dlog_se"], fmt="o", color="firebrick",
                markersize=6, label=f"Bin means (n_bins={len(bins)})")
    # Fit line
    xs = np.linspace(df[ai_col].min(), df[ai_col].max(), 50)
    ax.plot(xs, intercept + slope * xs, color="black", linewidth=1.5,
            label=f"OLS: slope = {slope:+.3f} (r={r:+.2f}, p={p:.2g})")
    ax.axhline(0, color="grey", linestyle=":", alpha=0.5)
    ax.set_xlabel(f"{ai_col}")
    ax.set_ylabel("Δ log(1+Q) [post − pre]")
    ax.set_title("Tag-level Δlog(questions) vs AI answerability")
    ax.legend(loc="lower left")
    fig.tight_layout()
    out_fig.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_fig, dpi=160)
    plt.close(fig)
    print(f"saved {out_fig}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--panel",
        type=Path,
        default=Path("data/processed/stackoverflow_question_type_master_panel.csv"),
    )
    p.add_argument(
        "--out-csv",
        type=Path,
        default=Path("outputs/tables/binscatter_ai_effect.csv"),
    )
    p.add_argument(
        "--out-fig",
        type=Path,
        default=Path("outputs/figures/binscatter_ai_effect.png"),
    )
    p.add_argument("--answerability", default="ai_answerability_zscore")
    p.add_argument("--n-bins", type=int, default=20)
    args = p.parse_args()
    main(args.panel, args.out_csv, args.out_fig, args.answerability, args.n_bins)
