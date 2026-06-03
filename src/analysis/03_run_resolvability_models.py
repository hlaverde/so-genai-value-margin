"""
Bloque 3 - Resolvability vs Quality.

Mide si, tras controlar volumen, las preguntas remanentes son mas o menos
resolvibles y de mejor o peor calidad. Outcomes (a nivel celda):

    accepted_share     = accepted_answer_questions / questions_count
    answered_share     = answered_questions / questions_count
    unanswered_share   = 1 - answered_share
    no_accepted_share  = 1 - accepted_share
    closed_share       = closed_questions / questions_count
    mean_answer_count  = answers / questions  (= answer_rate del master)

Modelo: weighted OLS (weights = questions_count), misma estructura DDD
del Bloque 2, cluster por tag, FE tag_qtype + week_id.

Adicional: tabla descriptiva pre/post x high/low AI (median split) sobre
body_length, accepted_share, answered_share, mean_answer_count, score,
closed_share, has_code (code_share).

Outputs:
    data/processed/resolvability_panel.csv
    outputs/models/resolvability_ddd_results.csv
    outputs/tables/table_resolvability_vs_quality.{tex,csv}
    outputs/tables/table_prepost_resolvability_by_ai_group.{tex,csv}
    outputs/figures/fig_resolvability_coefficients.{pdf,png}
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pyfixest.estimation import feols

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.paths import OUTPUTS_DIR, PROCESSED_DIR  # noqa: E402

FUNNEL_PANEL = PROCESSED_DIR / "reusable_artifact_funnel_panel.csv"
MASTER_PANEL = PROCESSED_DIR / "stackoverflow_question_type_master_panel.csv"
OUTPUT_PANEL = PROCESSED_DIR / "resolvability_panel.csv"

MODELS_DIR = OUTPUTS_DIR / "models"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"
for _d in (MODELS_DIR, TABLES_DIR, FIGURES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

AI_VAR = "ai_answerability_structural"

OUTCOMES: dict[str, str] = {
    "accepted_share": "Accepted share",
    "answered_share": "Answered share",
    "unanswered_share": "Unanswered share",
    "no_accepted_share": "No-accepted share",
    "closed_share": "Closed share",
    "mean_answer_count": "Mean answer count",
}

DESCRIPTIVE_VARS: dict[str, str] = {
    "body_length_mean": "Body length (chars)",
    "accepted_share": "Accepted share",
    "answered_share": "Answered share",
    "mean_answer_count": "Mean answer count",
    "avg_score": "Mean score",
    "closed_share": "Closed share",
    "code_share": "Code share",
}


def build_resolvability_panel() -> pd.DataFrame:
    print("[build] loading funnel panel ...")
    f = pd.read_csv(FUNNEL_PANEL)
    f["week_start"] = pd.to_datetime(f["week_start"])
    print(f"  funnel: {len(f):,} rows")

    print("[build] loading master panel (subset of cols) ...")
    master_cols = [
        "tag", "week_start", "question_type",
        "closed_questions", "closed_share",
        "avg_score", "body_length_mean",
        "code_questions", "code_share",
        "answers", "answer_rate",
    ]
    m = pd.read_csv(MASTER_PANEL, usecols=master_cols)
    m["week_start"] = pd.to_datetime(m["week_start"])
    print(f"  master: {len(m):,} rows")

    panel = f.merge(m, on=["tag", "week_start", "question_type"],
                    how="left", validate="1:1")
    print(f"[build] after merge: {len(panel):,} rows")

    # Outcomes derived
    qc = panel["questions_count"].astype(float)
    safe = qc.where(qc > 0, np.nan)
    panel["accepted_share_funnel"] = panel["accepted_answer_questions"] / safe
    panel["answered_share"] = panel["answered_questions"] / safe
    panel["unanswered_share"] = 1.0 - panel["answered_share"]
    panel["no_accepted_share"] = 1.0 - panel["accepted_share_funnel"]
    # Use master's closed_share & answer_rate for the actual model outcomes
    # to avoid divergent definitions; rename answer_rate -> mean_answer_count
    panel["mean_answer_count"] = panel["answer_rate"]
    # Overwrite accepted_share with the funnel-derived version (consistent)
    panel["accepted_share"] = panel["accepted_share_funnel"]
    return panel


def prepare_regressors(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    panel["tag_qtype"] = panel["tag"].astype(str) + "::" + panel["question_type"].astype(str)
    panel["week_id"] = panel["week_start"].dt.strftime("%Y-%m-%d")
    panel["ai"] = panel[AI_VAR].astype(float)
    panel["post"] = panel["post_chatgpt"].astype(int)
    panel["sub"] = panel["substitutable_type"].astype(int)
    panel["ai_post"] = panel["ai"] * panel["post"]
    panel["ai_sub"] = panel["ai"] * panel["sub"]
    panel["post_sub"] = panel["post"] * panel["sub"]
    panel["ai_post_sub"] = panel["ai"] * panel["post"] * panel["sub"]
    return panel


def fit_weighted_ddd(panel: pd.DataFrame, outcome: str):
    work = panel.dropna(subset=[outcome, "questions_count"]).copy()
    work = work[work["questions_count"] > 0]
    work["y"] = work[outcome].astype(float)
    work["w"] = work["questions_count"].astype(float)
    fml = "y ~ ai_post + ai_sub + post_sub + ai_post_sub | tag_qtype + week_id"
    return feols(fml, data=work, vcov={"CRV1": "tag"},
                 weights="w", weights_type="aweights")


def extract_triple(model) -> dict:
    coefs = model.coef()
    ses = model.se()
    pvals = model.pvalue()
    ci = model.confint()
    key = "ai_post_sub"
    low_col = "2.5%" if "2.5%" in ci.columns else "2.5 %"
    high_col = "97.5%" if "97.5%" in ci.columns else "97.5 %"
    return {
        "beta": float(coefs[key]),
        "se": float(ses[key]),
        "p": float(pvals[key]),
        "ci_low": float(ci.loc[key, low_col]),
        "ci_high": float(ci.loc[key, high_col]),
        "n_obs": int(model._N),
    }


def descriptive_prepost_by_ai(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.copy()
    med = p["ai"].median()
    p["ai_group"] = np.where(p["ai"] >= med, "HighAI", "LowAI")
    p["period"] = np.where(p["post"] == 1, "Post", "Pre")
    rows = []
    for var, label in DESCRIPTIVE_VARS.items():
        if var not in p.columns:
            continue
        for ai_g in ["LowAI", "HighAI"]:
            for per in ["Pre", "Post"]:
                sl = p[(p["ai_group"] == ai_g) & (p["period"] == per)]
                w = sl["questions_count"].astype(float)
                v = sl[var].astype(float)
                mask = v.notna() & (w > 0)
                if mask.sum() == 0:
                    mean = np.nan
                else:
                    mean = float(np.average(v[mask], weights=w[mask]))
                rows.append({
                    "variable": label, "ai_group": ai_g,
                    "period": per, "mean": mean,
                    "n_cells": int(mask.sum()),
                })
    df = pd.DataFrame(rows)
    return df


def pivot_descriptive(df: pd.DataFrame) -> pd.DataFrame:
    wide = df.pivot_table(
        index="variable",
        columns=["ai_group", "period"],
        values="mean",
        sort=False,
    )
    # Add delta cols
    wide[("LowAI", "Delta")] = wide[("LowAI", "Post")] - wide[("LowAI", "Pre")]
    wide[("HighAI", "Delta")] = wide[("HighAI", "Post")] - wide[("HighAI", "Pre")]
    wide[("DiD", "")] = wide[("HighAI", "Delta")] - wide[("LowAI", "Delta")]
    wide = wide[[
        ("LowAI", "Pre"), ("LowAI", "Post"), ("LowAI", "Delta"),
        ("HighAI", "Pre"), ("HighAI", "Post"), ("HighAI", "Delta"),
        ("DiD", ""),
    ]]
    return wide


def build_latex_table(results: pd.DataFrame) -> str:
    lines = []
    lines.append(r"\begin{table}[ht]")
    lines.append(r"\centering")
    lines.append(r"\caption{Triple-difference (DDD) effects on resolvability "
                 r"and quality outcomes at the tag-week-question-type cell. "
                 r"All regressions are weighted by cell question count "
                 r"and include tag$\times$qtype and week fixed effects; "
                 r"standard errors clustered at the tag level.}")
    lines.append(r"\label{tab:resolvability}")
    lines.append(r"\begin{tabular}{lrrrrr}")
    lines.append(r"\toprule")
    lines.append(r"Outcome & $\hat\beta_{DDD}$ & SE & $p$ & 95\% CI & N obs \\")
    lines.append(r"\midrule")
    for _, r in results.iterrows():
        ci = f"[{r['ci_low']:.4f}, {r['ci_high']:.4f}]"
        lines.append(
            f"{r['label']} & {r['beta']:.4f} & ({r['se']:.4f}) & "
            f"{r['p']:.4f} & {ci} & {r['n_obs']:,} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


def build_descriptive_latex(wide: pd.DataFrame) -> str:
    lines = []
    lines.append(r"\begin{table}[ht]")
    lines.append(r"\centering")
    lines.append(r"\caption{Pre/post means by AI-answerability group "
                 r"(median split on AI structural index). Means are "
                 r"weighted by cell question count. Delta = Post $-$ Pre; "
                 r"DiD = HighAI Delta $-$ LowAI Delta.}")
    lines.append(r"\label{tab:prepost_resolvability_by_ai_group}")
    lines.append(r"\begin{tabular}{lrrrrrrr}")
    lines.append(r"\toprule")
    lines.append(r" & \multicolumn{3}{c}{LowAI} & \multicolumn{3}{c}{HighAI} & DiD \\")
    lines.append(r"\cmidrule(lr){2-4} \cmidrule(lr){5-7}")
    lines.append(r"Variable & Pre & Post & $\Delta$ & Pre & Post & $\Delta$ & \\")
    lines.append(r"\midrule")
    for var, row in wide.iterrows():
        lines.append(
            f"{var} & "
            f"{row[('LowAI','Pre')]:.4f} & {row[('LowAI','Post')]:.4f} & "
            f"{row[('LowAI','Delta')]:+.4f} & "
            f"{row[('HighAI','Pre')]:.4f} & {row[('HighAI','Post')]:.4f} & "
            f"{row[('HighAI','Delta')]:+.4f} & "
            f"{row[('DiD','')]:+.4f} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


def build_coefplot(results: pd.DataFrame, dest_pdf: Path, dest_png: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4.0), dpi=200)
    ordered = [OUTCOMES[k] for k in OUTCOMES]
    y_pos = np.arange(len(ordered))[::-1]
    label_to_row = {r["label"]: r for _, r in results.iterrows()}
    betas = [label_to_row[lbl]["beta"] for lbl in ordered]
    err_lo = [label_to_row[lbl]["beta"] - label_to_row[lbl]["ci_low"] for lbl in ordered]
    err_hi = [label_to_row[lbl]["ci_high"] - label_to_row[lbl]["beta"] for lbl in ordered]
    ax.errorbar(betas, y_pos, xerr=[err_lo, err_hi],
                fmt="o", color="#1a1a1a", ecolor="#1a1a1a",
                elinewidth=1.2, capsize=3, markersize=5)
    ax.axvline(0, color="#888888", linestyle="--", linewidth=0.8)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(ordered)
    ax.set_xlabel(r"DDD coefficient $\hat\beta$ on AI$\cdot$Post$\cdot$Sub (95% CI)")
    ax.set_title("Resolvability and quality outcomes\n"
                 "Triple-difference effects after ChatGPT (2022-11-30)",
                 fontsize=10)
    ax.grid(axis="x", linestyle=":", linewidth=0.6, alpha=0.6)
    fig.tight_layout()
    fig.savefig(dest_pdf, bbox_inches="tight")
    fig.savefig(dest_png, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    print(f"[main] start {datetime.now().isoformat(timespec='seconds')}")
    panel = build_resolvability_panel()
    panel.to_csv(OUTPUT_PANEL, index=False)
    print(f"[main] wrote {OUTPUT_PANEL} ({OUTPUT_PANEL.stat().st_size/1e6:.1f} MB)")
    panel = prepare_regressors(panel)

    rows: list[dict] = []
    for col, label in OUTCOMES.items():
        print(f"\n[main] fitting {col} ({label})...")
        m = fit_weighted_ddd(panel, col)
        est = extract_triple(m)
        rows.append({"outcome": col, "label": label, **est})
        print(f"  beta_DDD={est['beta']:.4f}  SE={est['se']:.4f}  p={est['p']:.4f}  "
              f"N={est['n_obs']:,}")

    results = pd.DataFrame(rows)
    results.to_csv(MODELS_DIR / "resolvability_ddd_results.csv", index=False)
    results.to_csv(TABLES_DIR / "table_resolvability_vs_quality.csv", index=False)
    (TABLES_DIR / "table_resolvability_vs_quality.tex").write_text(
        build_latex_table(results), encoding="utf-8")

    print("\n[main] descriptive pre/post by AI group ...")
    desc = descriptive_prepost_by_ai(panel)
    desc.to_csv(MODELS_DIR / "resolvability_prepost_long.csv", index=False)
    wide = pivot_descriptive(desc)
    wide.to_csv(TABLES_DIR / "table_prepost_resolvability_by_ai_group.csv")
    (TABLES_DIR / "table_prepost_resolvability_by_ai_group.tex").write_text(
        build_descriptive_latex(wide), encoding="utf-8")

    print("[main] coefplot ...")
    build_coefplot(
        results,
        FIGURES_DIR / "fig_resolvability_coefficients.pdf",
        FIGURES_DIR / "fig_resolvability_coefficients.png",
    )
    print(f"\n[main] done {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
