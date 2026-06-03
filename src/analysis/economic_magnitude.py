"""Magnitud económica del shock: preguntas "perdidas" atribuibles a IA.

Tres aproximaciones:

(1) Naive: total questions pre vs post, asume contrafactual = pre trend.
    Limitación: ignora que SO ya caía antes de ChatGPT.

(2) Linear extrapolation: extrapola log(Q_weekly) usando OLS sobre el
    periodo pre-ChatGPT, predice contrafactual post, restamos del
    observado. Da la "pérdida atribuible al shock" condicional a que
    el trend pre habría continuado linealmente.

(3) DDD-implied: usando β_DDD y el rango de AI answerability, computa
    el delta marginal atribuible al canal AI específicamente
    (excluye declive general por otras causas).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")
BETA_DDD = -0.137791  # de DDD baseline


def main(panel_path: Path, out_dir: Path, ai_col: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(panel_path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["period"] = np.where(df["week_start"] < CHATGPT_RELEASE, "pre", "post")

    weekly = (
        df.groupby("week_start")["questions"].sum().reset_index().sort_values("week_start")
    )
    weekly["log_q"] = np.log(weekly["questions"].clip(lower=1))
    weekly["t"] = ((weekly["week_start"] - weekly["week_start"].min()).dt.days // 7).astype(int)

    pre_mask = weekly["week_start"] < CHATGPT_RELEASE
    pre = weekly[pre_mask]
    post = weekly[~pre_mask]

    # ===== (1) Naive =====
    naive_pre_avg = pre["questions"].mean()
    naive_post_avg = post["questions"].mean()
    naive_delta_week = naive_post_avg - naive_pre_avg
    naive_total_loss = naive_delta_week * len(post)
    print("=== (1) NAIVE ===")
    print(f"  pre weekly avg:  {naive_pre_avg:>10,.0f}")
    print(f"  post weekly avg: {naive_post_avg:>10,.0f}")
    print(f"  delta per week:  {naive_delta_week:>+10,.0f}")
    print(f"  total over {len(post)} post weeks: {naive_total_loss:>+10,.0f}")

    # ===== (2) Linear extrapolation pre -> post =====
    # Fit log(Q) ~ t on pre
    from scipy.stats import linregress
    fit = linregress(pre["t"].values, pre["log_q"].values)
    print(f"\n=== (2) LINEAR EXTRAPOLATION ===")
    print(f"  pre slope (log/week): {fit.slope:+.5f} (R^2 = {fit.rvalue**2:.3f})")
    # Predict counterfactual post
    post_t = post["t"].values
    cf_log = fit.intercept + fit.slope * post_t
    cf_q = np.exp(cf_log)
    actual_q = post["questions"].values
    diff_q = actual_q - cf_q
    total_loss = diff_q.sum()
    print(f"  Counterfactual total over post: {cf_q.sum():,.0f}")
    print(f"  Actual total over post:         {actual_q.sum():,.0f}")
    print(f"  Implied LOSS:                   {total_loss:+,.0f}")
    print(f"  % implied lost relative to CF:  {total_loss / cf_q.sum() * 100:+.1f}%")

    # Persist CF series
    post["cf_questions"] = cf_q
    post["loss"] = actual_q - cf_q
    weekly_cf = weekly.merge(
        post[["week_start", "cf_questions", "loss"]], on="week_start", how="left"
    )
    weekly_cf.to_csv(out_dir / "economic_magnitude_weekly.csv", index=False)

    # ===== (3) DDD-implied marginal effect =====
    # β_DDD * AI_t aplicado al universo sub × post
    ans = df[["tag", ai_col]].drop_duplicates().set_index("tag")
    sub_post = df[(df["substitutable_type"] == 1) & (df["period"] == "post")].copy()
    sub_post = sub_post.merge(ans, on="tag", suffixes=("", "_dup"))
    # Para cada tag-week-qtype, el efecto MARGINAL de AI es:
    #   exp(β_DDD * ai) - 1 (semi-elasticity en log(1+Q))
    # Si ai = 0 (mean): efecto = 0
    # Si ai > 0: caída adicional
    # El total "perdido por AI" = sum over (tag, week, qtype) sustituible post:
    #   Q_observado × (exp(-β_DDD * ai) - 1)
    sub_post["counterfactual_factor"] = np.exp(-BETA_DDD * sub_post[ai_col])  # 1 + |β|*ai aprox
    sub_post["cf_questions"] = sub_post["questions"] * sub_post["counterfactual_factor"]
    sub_post["attributable_loss"] = sub_post["cf_questions"] - sub_post["questions"]
    total_attributable = sub_post["attributable_loss"].sum()
    observed_post_sub = sub_post["questions"].sum()
    print(f"\n=== (3) DDD-ATTRIBUTABLE (channel AI×Sub specifically) ===")
    print(f"  Observed substitutable questions post: {observed_post_sub:,.0f}")
    print(f"  Counterfactual under AI=0:             {(observed_post_sub + total_attributable):,.0f}")
    print(f"  Attributable additional loss:          {total_attributable:+,.0f}")
    print(f"  % attributable to AI channel:           {total_attributable / (observed_post_sub + total_attributable) * 100:+.1f}%")

    summary = pd.DataFrame([
        {
            "approach": "naive_avg_difference",
            "implied_loss": naive_total_loss,
            "comment": "Simple diff; ignores pre-trend",
        },
        {
            "approach": "linear_extrapolation",
            "implied_loss": total_loss,
            "comment": f"pre-OLS slope {fit.slope:+.5f}/week",
        },
        {
            "approach": "ddd_ai_channel",
            "implied_loss": total_attributable,
            "comment": f"only AI-attributable; beta={BETA_DDD}",
        },
    ])
    summary.to_csv(out_dir / "economic_magnitude_summary.csv", index=False)
    print("\nsaved economic_magnitude_summary.csv")

    # ===== Figura =====
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(weekly["week_start"], weekly["questions"], color="black", linewidth=1.0, label="Observed")
    cf_full = np.concatenate([pre["questions"].values, cf_q])
    ax.plot(weekly["week_start"], cf_full, color="steelblue", linewidth=1.5,
            linestyle="--", label="Linear extrapolation of pre-trend")
    ax.fill_between(
        post["week_start"], post["questions"], cf_q,
        color="firebrick", alpha=0.25, label="Implied loss",
    )
    ax.axvline(CHATGPT_RELEASE, color="firebrick", linestyle=":", alpha=0.8)
    ax.set_ylabel("Questions per week (top-100 tags)")
    ax.set_title("Counterfactual under pre-ChatGPT trend extrapolation")
    ax.legend(loc="upper right")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    fig_path = out_dir.parent / "figures" / "economic_magnitude_counterfactual.png"
    fig.savefig(fig_path, dpi=160)
    plt.close(fig)
    print(f"saved figure {fig_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--panel",
        type=Path,
        default=Path("data/processed/stackoverflow_question_type_master_panel.csv"),
    )
    p.add_argument("--out-dir", type=Path, default=Path("outputs/tables"))
    p.add_argument("--answerability", default="ai_answerability_zscore")
    args = p.parse_args()
    main(args.panel, args.out_dir, args.answerability)
