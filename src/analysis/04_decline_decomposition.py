"""
Bloque 4 - Decline decomposition: aggregate decline vs DDD-identified channel.

Question: of the total observed post-period shortfall in weekly questions
(relative to a no-shock counterfactual trend extrapolated from pre data),
how much is explained by the DDD-identified channel (AI x Sub x Post)
and how much is residual?

Steps:
  1. Observed: total pre, total post, weekly avg pre/post.
  2. Trend-implied counterfactual: fit log(weekly_total) ~ t on pre-only,
     extrapolate to post weeks; trend_shortfall = sum(trend_cf - observed_post).
  3. DDD channel: implied_displaced from Bloque 2 (questions_count outcome).
  4. Share: ddd_channel_share_of_trend_shortfall = ddd_displaced / trend_shortfall.
  5. Residual: trend_shortfall - ddd_displaced.

Outputs:
    outputs/models/decline_decomposition.csv
    outputs/tables/table_decline_decomposition.{tex,csv}
    outputs/figures/fig_decline_decomposition.{pdf,png}
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.paths import OUTPUTS_DIR, PROCESSED_DIR  # noqa: E402

PANEL = PROCESSED_DIR / "reusable_artifact_funnel_panel.csv"
DDD_RESULTS = OUTPUTS_DIR / "models" / "reusable_funnel_ddd_results.csv"

MODELS_DIR = OUTPUTS_DIR / "models"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"
for _d in (MODELS_DIR, TABLES_DIR, FIGURES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

CUTOFF = pd.Timestamp("2022-11-30")


def aggregate_weekly_totals(panel: pd.DataFrame) -> pd.DataFrame:
    g = (panel.groupby("week_start", as_index=False)
         .agg(weekly_questions=("questions_count", "sum"),
              weekly_reusable=("reusable_artifacts", "sum")))
    g["week_start"] = pd.to_datetime(g["week_start"])
    g = g.sort_values("week_start").reset_index(drop=True)
    g["t"] = np.arange(len(g))
    g["post"] = (g["week_start"] >= CUTOFF).astype(int)
    return g


def fit_pre_trend(weekly: pd.DataFrame, target_col: str = "weekly_questions") -> tuple[float, float]:
    pre = weekly[weekly["post"] == 0].copy()
    pre["log_y"] = np.log(pre[target_col])
    slope, intercept = np.polyfit(pre["t"].values, pre["log_y"].values, deg=1)
    return float(slope), float(intercept)


def trend_extrapolation(weekly: pd.DataFrame, slope: float, intercept: float) -> pd.DataFrame:
    weekly = weekly.copy()
    weekly["log_trend_fit"] = intercept + slope * weekly["t"]
    weekly["trend_fit"] = np.exp(weekly["log_trend_fit"])
    return weekly


def decompose(weekly: pd.DataFrame, ddd_displaced: float, target_col: str) -> dict:
    pre = weekly[weekly["post"] == 0]
    post = weekly[weekly["post"] == 1]
    obs_pre_total = float(pre[target_col].sum())
    obs_post_total = float(post[target_col].sum())
    n_pre = len(pre)
    n_post = len(post)
    pre_weekly_mean = obs_pre_total / max(n_pre, 1)
    post_weekly_mean = obs_post_total / max(n_post, 1)

    trend_cf_post_total = float(post["trend_fit"].sum())
    trend_shortfall = trend_cf_post_total - obs_post_total
    residual = trend_shortfall - ddd_displaced
    ddd_share = ddd_displaced / trend_shortfall if trend_shortfall != 0 else np.nan

    return {
        "target": target_col,
        "n_pre_weeks": n_pre,
        "n_post_weeks": n_post,
        "observed_pre_total": obs_pre_total,
        "observed_post_total": obs_post_total,
        "observed_pre_weekly_avg": pre_weekly_mean,
        "observed_post_weekly_avg": post_weekly_mean,
        "observed_drop_weekly": pre_weekly_mean - post_weekly_mean,
        "trend_cf_post_total": trend_cf_post_total,
        "trend_shortfall": trend_shortfall,
        "ddd_displaced": ddd_displaced,
        "residual_after_ddd": residual,
        "ddd_share_of_trend_shortfall": ddd_share,
    }


def build_latex_table(dec_q: dict, dec_r: dict) -> str:
    def fmt(v): return f"{v:,.0f}" if abs(v) >= 1 else f"{v:.4f}"
    lines = []
    lines.append(r"\begin{table}[ht]")
    lines.append(r"\centering")
    lines.append(r"\caption{Decomposition of the post-ChatGPT decline in "
                 r"Stack Overflow into (i) the aggregate trend-implied shortfall "
                 r"and (ii) the share attributable to the DDD-identified "
                 r"AI$\cdot$Sub$\cdot$Post channel. The DDD channel quantifies "
                 r"only the marginal effect identified by the triple difference. "
                 r"The residual reflects all other co-occurring sources of "
                 r"decline (secular trends, platform policies, macro shocks).}")
    lines.append(r"\label{tab:decline_decomposition}")
    lines.append(r"\begin{tabular}{lrr}")
    lines.append(r"\toprule")
    lines.append(r" & Questions (all) & Reusable artifacts \\")
    lines.append(r"\midrule")
    lines.append(f"Pre weeks & {dec_q['n_pre_weeks']:,} & {dec_r['n_pre_weeks']:,} \\\\")
    lines.append(f"Post weeks & {dec_q['n_post_weeks']:,} & {dec_r['n_post_weeks']:,} \\\\")
    lines.append(f"Pre weekly avg & {fmt(dec_q['observed_pre_weekly_avg'])} & "
                 f"{fmt(dec_r['observed_pre_weekly_avg'])} \\\\")
    lines.append(f"Post weekly avg & {fmt(dec_q['observed_post_weekly_avg'])} & "
                 f"{fmt(dec_r['observed_post_weekly_avg'])} \\\\")
    lines.append(r"\midrule")
    lines.append(f"Observed post total & {fmt(dec_q['observed_post_total'])} & "
                 f"{fmt(dec_r['observed_post_total'])} \\\\")
    lines.append(f"Trend-implied CF total & {fmt(dec_q['trend_cf_post_total'])} & "
                 f"{fmt(dec_r['trend_cf_post_total'])} \\\\")
    lines.append(f"Trend-implied shortfall & {fmt(dec_q['trend_shortfall'])} & "
                 f"{fmt(dec_r['trend_shortfall'])} \\\\")
    lines.append(r"\midrule")
    lines.append(f"DDD-identified displacement & {fmt(dec_q['ddd_displaced'])} & "
                 f"{fmt(dec_r['ddd_displaced'])} \\\\")
    lines.append(f"DDD / shortfall share & "
                 f"{dec_q['ddd_share_of_trend_shortfall']*100:.1f}\\% & "
                 f"{dec_r['ddd_share_of_trend_shortfall']*100:.1f}\\% \\\\")
    lines.append(f"Residual after DDD & {fmt(dec_q['residual_after_ddd'])} & "
                 f"{fmt(dec_r['residual_after_ddd'])} \\\\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


def build_stacked_bar(dec_q: dict, dec_r: dict, dest_pdf: Path, dest_png: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 5.2), dpi=200)
    cats = ["Questions (all)", "Reusable artifacts"]
    ddd_vals = [dec_q["ddd_displaced"], dec_r["ddd_displaced"]]
    res_vals = [dec_q["residual_after_ddd"], dec_r["residual_after_ddd"]]
    totals = [d + r for d, r in zip(ddd_vals, res_vals)]
    max_total = max(totals)

    x = np.arange(len(cats))
    ax.bar(x, ddd_vals, color="#9c2a2a",
           label="DDD-identified channel (AI$\\cdot$Sub$\\cdot$Post)")
    ax.bar(x, res_vals, bottom=ddd_vals, color="#cccccc",
           label="Residual (trend, policy, macro)")

    # Headroom so the title/legend never overlap
    ax.set_ylim(top=max_total * 1.30)

    for i, (d, r, tot) in enumerate(zip(ddd_vals, res_vals, totals)):
        # Total shortfall above the bar (below the headroom)
        ax.text(i, tot + max_total * 0.04,
                f"Total shortfall: {tot:,.0f}\nDDD share: {d/tot*100:.1f}%",
                ha="center", va="bottom", fontsize=9, weight="semibold")
        # DDD number: place INSIDE if bar tall enough, else OUTSIDE to the right
        if d > max_total * 0.04:
            ax.text(i, d / 2, f"{d:,.0f}",
                    ha="center", va="center", color="white", fontsize=8.5)
        else:
            ax.annotate(
                f"DDD: {d:,.0f}",
                xy=(i + 0.42, d / 2),
                xytext=(i + 0.62, max_total * 0.22),
                fontsize=8.5, color="#9c2a2a",
                arrowprops=dict(arrowstyle="-", color="#9c2a2a", lw=0.8),
            )
        # Residual mid
        ax.text(i, d + r / 2, f"{r:,.0f}",
                ha="center", va="center", color="#444444", fontsize=8.5)

    ax.set_xticks(x)
    ax.set_xticklabels(cats)
    ax.set_ylabel("Cumulative units in 109-week post window")
    ax.set_title("Decline decomposition: aggregate trend shortfall\n"
                 "vs. DDD-identified AI$\\cdot$Sub$\\cdot$Post channel",
                 fontsize=10)
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
    fig.tight_layout()
    fig.savefig(dest_pdf, bbox_inches="tight")
    fig.savefig(dest_png, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    print(f"[main] start {datetime.now().isoformat(timespec='seconds')}")
    panel = pd.read_csv(PANEL)
    weekly = aggregate_weekly_totals(panel)
    print(f"[main] weekly aggregated: {len(weekly)} weeks "
          f"({weekly['week_start'].min().date()} to {weekly['week_start'].max().date()})")
    n_pre = int((weekly["post"] == 0).sum())
    n_post = int((weekly["post"] == 1).sum())
    print(f"[main] pre weeks: {n_pre}, post weeks: {n_post}")

    # Fit pre-trend on log(weekly_questions)
    slope_q, intercept_q = fit_pre_trend(weekly, "weekly_questions")
    slope_r, intercept_r = fit_pre_trend(weekly, "weekly_reusable")
    weekly = trend_extrapolation(weekly, slope_q, intercept_q)
    weekly = weekly.rename(columns={"trend_fit": "trend_fit_q",
                                    "log_trend_fit": "log_trend_fit_q"})
    weekly["log_trend_fit_r"] = intercept_r + slope_r * weekly["t"]
    weekly["trend_fit_r"] = np.exp(weekly["log_trend_fit_r"])
    print(f"[main] pre-trend slope (log questions per week): {slope_q:.5f}")
    print(f"[main] pre-trend slope (log reusable per week):  {slope_r:.5f}")

    # Load DDD-identified displacement
    ddd = pd.read_csv(DDD_RESULTS)
    impl_q = float(ddd[ddd["outcome"] == "questions_count"]["implied_displaced"].iloc[0])
    impl_r = float(ddd[ddd["outcome"] == "reusable_artifacts"]["implied_displaced"].iloc[0])
    print(f"[main] DDD-implied displaced (questions): {impl_q:,.0f}")
    print(f"[main] DDD-implied displaced (reusable):  {impl_r:,.0f}")

    # Decompose for questions
    weekly_q = weekly[["week_start", "weekly_questions", "trend_fit_q", "post", "t"]].copy()
    weekly_q = weekly_q.rename(columns={"trend_fit_q": "trend_fit"})
    dec_q = decompose(weekly_q, impl_q, "weekly_questions")
    # Decompose for reusable
    weekly_r = weekly[["week_start", "weekly_reusable", "trend_fit_r", "post", "t"]].copy()
    weekly_r = weekly_r.rename(columns={"trend_fit_r": "trend_fit"})
    dec_r = decompose(weekly_r, impl_r, "weekly_reusable")

    print("\n[main] decomposition (questions):")
    for k, v in dec_q.items():
        print(f"  {k}: {v}")
    print("\n[main] decomposition (reusable):")
    for k, v in dec_r.items():
        print(f"  {k}: {v}")

    rows = pd.DataFrame([dec_q, dec_r])
    rows.to_csv(MODELS_DIR / "decline_decomposition.csv", index=False)
    rows.to_csv(TABLES_DIR / "table_decline_decomposition.csv", index=False)
    (TABLES_DIR / "table_decline_decomposition.tex").write_text(
        build_latex_table(dec_q, dec_r), encoding="utf-8")
    build_stacked_bar(
        dec_q, dec_r,
        FIGURES_DIR / "fig_decline_decomposition.pdf",
        FIGURES_DIR / "fig_decline_decomposition.png",
    )

    # Sanity vs baseline expectations
    print("\n[main] SANITY:")
    print(f"  Pre weekly avg (questions): {dec_q['observed_pre_weekly_avg']:,.0f} "
          f"(baseline expectation ~44,159)")
    print(f"  Post weekly avg (questions): {dec_q['observed_post_weekly_avg']:,.0f} "
          f"(baseline expectation ~15,332)")
    print(f"  Trend shortfall (questions): {dec_q['trend_shortfall']:,.0f} "
          f"(baseline expectation ~1.42M)")
    print(f"  DDD share of shortfall: {dec_q['ddd_share_of_trend_shortfall']*100:.1f}% "
          f"(baseline expectation ~4%)")
    print(f"\n[main] done {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
