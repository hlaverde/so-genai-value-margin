"""
Action 1 (DSS scope artefact): Value-conditioned replenishment monitor.

Bloque 0 (sanity gate, Rule 3): reproduce the baseline DDD beta on the
  master panel and fail loudly if |beta - (-0.108)| > 0.03.

Bloque 1 (the artefact): build a per-tag value-to-displacement indicator
  VtD_t = (implied displaced high-value funnel posts)_t
          / (implied displaced activity)_t
  applied cell-by-cell from the estimated DDD coefficients (no new
  identification, no raw reload -- reuses the validated value-weighted
  funnel panel and the published betas).

  Decision rule: benign-pruning predicts the displaced posts are LOWER
  value than the surviving mix, so VtD_t should not exceed the
  pre-period high-value share theta. Tags with VtD_t > theta are flagged:
  the displacement is reaching the crowd-validated margin locally and an
  activity-count monitor understates the high-value loss.

  Backtest: compare the tag ranking a manager sees under the standard
  activity-deficit metric against the ranking under VtD, and quantify how
  many high-VtD tags the activity metric misses.

Outputs:
  outputs/models/vtd_monitor_by_tag.csv
  outputs/models/vtd_monitor_summary.csv
  outputs/tables/table_vtd_monitor.tex
  outputs/figures/fig_vtd_monitor.pdf
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.paths import PROCESSED_DIR, OUTPUTS_DIR  # noqa: E402

CHATGPT = pd.Timestamp("2022-11-30")
MASTER = PROCESSED_DIR / "stackoverflow_question_type_master_panel.csv"
VW = PROCESSED_DIR / "value_weighted_funnel_panel.csv"
MODELS = OUTPUTS_DIR / "models"
TABLES = OUTPUTS_DIR / "tables"
FIGURES = OUTPUTS_DIR / "figures"
for _d in (MODELS, TABLES, FIGURES):
    _d.mkdir(parents=True, exist_ok=True)

AI = "ai_answerability_structural"

# Published DDD betas (value_weighted_funnel_ddd_results.csv):
BETA_ACTIVITY = -0.108     # questions baseline
BETA_HV1 = -0.131          # high-value, score >= 1 (crowd-validated)


# ---------------- Bloque 0: sanity gate ----------------
def sanity_gate() -> float:
    df = pd.read_csv(MASTER)
    df["week_id"] = pd.to_datetime(df["week_start"]).dt.strftime("%Y-%m-%d")
    df["ai"] = df[AI].astype(float)
    df["sub"] = df["substitutable_type"].astype(int)
    df["post"] = df["post_chatgpt"].astype(int)
    df["ai_post"] = df["ai"] * df["post"]
    df["ai_sub"] = df["ai"] * df["sub"]
    df["post_sub"] = df["post"] * df["sub"]
    df["ai_post_sub"] = df["ai"] * df["post"] * df["sub"]
    fml = ("log_questions_p1 ~ ai_post + ai_sub + post_sub + ai_post_sub "
           "| tag_qtype + week_id")
    m = pf.feols(fml, data=df, vcov={"CRV1": "tag"})
    beta = float(m.coef()["ai_post_sub"])
    print(f"[gate] baseline ai_post_sub beta = {beta:.4f} "
          f"(target -0.108)")
    if abs(beta - (-0.108)) > 0.03:
        raise SystemExit(f"[gate] FAIL: |{beta:.4f} - (-0.108)| > 0.03")
    print("[gate] PASS")
    return beta


# ---------------- Bloque 1: VtD monitor ----------------
def build_vtd() -> tuple[pd.DataFrame, dict]:
    p = pd.read_csv(VW)
    p["week_start"] = pd.to_datetime(p["week_start"])
    p["ai"] = p[AI].astype(float)
    p["sub"] = p["substitutable_type"].astype(int)
    p["post"] = (p["week_start"] >= CHATGPT).astype(int)

    # Cell-by-cell implied displacement (counterfactual - observed) on the
    # post-period cells.  factor = exp(-beta * ai * sub) >= 1 for beta<0.
    post = p[p["post"] == 1].copy()
    g = post["ai"] * post["sub"]
    post["disp_activity"] = post["questions_count"] * (np.exp(-BETA_ACTIVITY * g) - 1.0)
    post["disp_hv"] = post["high_value_artifacts"] * (np.exp(-BETA_HV1 * g) - 1.0)

    by_tag = (post.groupby("tag")
              .agg(disp_activity=("disp_activity", "sum"),
                   disp_hv=("disp_hv", "sum"),
                   ai=("ai", "first"))
              .reset_index())
    by_tag = by_tag[by_tag["disp_activity"] > 0].copy()
    by_tag["VtD"] = by_tag["disp_hv"] / by_tag["disp_activity"]

    # theta: pre-period platform high-value share (benign-pruning benchmark)
    pre = p[p["post"] == 0]
    theta = pre["high_value_artifacts"].sum() / pre["questions_count"].sum()

    by_tag["flag"] = (by_tag["VtD"] > theta).astype(int)
    by_tag = by_tag.sort_values("VtD", ascending=False).reset_index(drop=True)

    # Backtest: activity-deficit ranking vs VtD ranking
    by_tag["rank_activity"] = by_tag["disp_activity"].rank(ascending=False)
    by_tag["rank_vtd"] = by_tag["VtD"].rank(ascending=False)
    rho, p_rho = spearmanr(by_tag["rank_activity"], by_tag["rank_vtd"])

    k = 10
    top_vtd = set(by_tag.nsmallest(k, "rank_vtd")["tag"])
    top_act = set(by_tag.nsmallest(k, "rank_activity")["tag"])
    missed = top_vtd - top_act

    agg_vtd = by_tag["disp_hv"].sum() / by_tag["disp_activity"].sum()

    summary = {
        "theta_pre_hv_share": theta,
        "aggregate_VtD": agg_vtd,
        "n_tags": len(by_tag),
        "n_flagged": int(by_tag["flag"].sum()),
        "share_flagged": by_tag["flag"].mean(),
        "spearman_activity_vs_vtd": rho,
        "spearman_p": p_rho,
        "top10_vtd_missed_by_activity": len(missed),
        "missed_tags": ";".join(sorted(missed)),
    }
    return by_tag, summary


def write_outputs(by_tag: pd.DataFrame, summary: dict) -> None:
    by_tag.to_csv(MODELS / "vtd_monitor_by_tag.csv", index=False)
    pd.DataFrame([summary]).to_csv(MODELS / "vtd_monitor_summary.csv",
                                   index=False)

    print("\n[VtD] summary")
    for kk, vv in summary.items():
        if isinstance(vv, float):
            print(f"  {kk}: {vv:.4f}")
        else:
            print(f"  {kk}: {vv}")
    print("\n[VtD] top-12 tags by VtD:")
    print(by_tag.head(12)[["tag", "disp_activity", "disp_hv",
                            "VtD", "rank_activity", "flag"]]
          .to_string(index=False))

    # LaTeX table: top-10 by VtD with their activity-deficit rank
    theta = summary["theta_pre_hv_share"]
    head = by_tag.head(10)
    lines = [
        r"\begin{table}[ht]", r"\centering",
        r"\caption{Value-conditioned replenishment monitor: the ten tags "
        r"with the highest VtD ratio (implied displaced high-value "
        r"funnel-qualified posts divided by implied displaced activity). "
        r"The benign-pruning benchmark is the pre-period high-value share "
        rf"$\theta = {theta:.3f}$; tags with $\text{{VtD}} > \theta$ are "
        r"flagged. ``Activity rank'' is the tag's position under the "
        r"standard activity-deficit metric a manager would otherwise "
        r"monitor; a high VtD rank paired with a low activity rank is "
        r"precisely the high-value erosion an activity-count monitor "
        r"misses.}",
        r"\label{tab:vtd_monitor}",
        r"\small",
        r"\begin{tabular}{lrrrc}", r"\toprule",
        r"Tag & Displaced activity & Displaced high-value & VtD & "
        r"Activity rank \\", r"\midrule",
    ]
    for _, r in head.iterrows():
        lines.append(
            f"\\texttt{{{r['tag']}}} & {r['disp_activity']:,.0f} & "
            f"{r['disp_hv']:,.0f} & {r['VtD']:.3f} & "
            f"{int(r['rank_activity'])} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    (TABLES / "table_vtd_monitor.tex").write_text("\n".join(lines),
                                                  encoding="utf-8")

    # Figure: VtD vs activity-deficit rank scatter
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(by_tag["rank_activity"], by_tag["VtD"], s=18,
               c=np.where(by_tag["flag"] == 1, "tab:red", "tab:gray"),
               alpha=0.7)
    ax.axhline(summary["theta_pre_hv_share"], ls="--", c="black", lw=1,
               label=rf"$\theta$ = {summary['theta_pre_hv_share']:.3f} "
                     f"(benign-pruning benchmark)")
    ax.set_xlabel("Tag rank under standard activity-deficit metric "
                  "(1 = largest)")
    ax.set_ylabel("VtD = displaced high-value / displaced activity")
    ax.set_title("Value-conditioned monitor vs activity-count metric")
    ax.legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGURES / "fig_vtd_monitor.pdf")
    print(f"\n[VtD] wrote table + figure")


def main():
    sanity_gate()
    by_tag, summary = build_vtd()
    write_outputs(by_tag, summary)


if __name__ == "__main__":
    main()
