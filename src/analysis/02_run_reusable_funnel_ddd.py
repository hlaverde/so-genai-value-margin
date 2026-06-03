"""
Bloque 2 - DDD por outcome del Reusable Artifact Funnel.

Para cada Y in {questions_count, answered_questions, accepted_answer_questions,
                accepted_nonclosed_questions, accepted_nonnegative_questions,
                reusable_artifacts}:

    log(1 + Y_twk) ~ ai_post + ai_sub + post_sub + ai_post_sub
                    | tag_qtype + week_id    (cluster: tag)

donde:
    ai  = ai_answerability_structural (medida principal del paper v7)
    post= 1{week >= 2022-11-30}
    sub = substitutable_type (1 si tipo sustituible por LLM)

El coeficiente DDD es ai_post_sub (interaccion triple).

Implied displacement (counts only):
    Y_cf  = Y_obs * exp(-beta * AI * Sub)  en celdas post
    impl_disp = sum(Y_cf - Y_obs)

Outputs:
    outputs/models/reusable_funnel_ddd_results.csv
    outputs/tables/table_reusable_funnel.tex
    outputs/tables/table_reusable_funnel.csv
    outputs/figures/fig_reusable_funnel_coefficients.pdf (+.png)
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

PANEL = PROCESSED_DIR / "reusable_artifact_funnel_panel.csv"
MODELS_DIR = OUTPUTS_DIR / "models"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"
for _d in (MODELS_DIR, TABLES_DIR, FIGURES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

OUTCOMES: dict[str, str] = {
    "questions_count": "Questions",
    "answered_questions": "Answered",
    "accepted_answer_questions": "Accepted answer",
    "accepted_nonclosed_questions": "Accepted, not closed",
    "accepted_nonnegative_questions": "Accepted, score >= 0",
    "reusable_artifacts": "Reusable artifact",
}

AI_VAR = "ai_answerability_structural"
CUTOFF = "2022-11-30"


def prepare_panel() -> pd.DataFrame:
    df = pd.read_csv(PANEL)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["tag_qtype"] = df["tag"].astype(str) + "::" + df["question_type"].astype(str)
    df["week_id"] = df["week_start"].dt.strftime("%Y-%m-%d")
    df["ai"] = df[AI_VAR].astype(float)
    df["post"] = df["post_chatgpt"].astype(int)
    df["sub"] = df["substitutable_type"].astype(int)
    df["ai_post"] = df["ai"] * df["post"]
    df["ai_sub"] = df["ai"] * df["sub"]
    df["post_sub"] = df["post"] * df["sub"]
    df["ai_post_sub"] = df["ai"] * df["post"] * df["sub"]
    return df


def fit_ddd(df: pd.DataFrame, outcome: str):
    work = df.copy()
    work["log_y"] = np.log1p(work[outcome])
    fml = (
        "log_y ~ ai_post + ai_sub + post_sub + ai_post_sub "
        "| tag_qtype + week_id"
    )
    return feols(fml, data=work, vcov={"CRV1": "tag"})


def implied_displacement(df: pd.DataFrame, outcome: str, beta: float) -> float:
    post = df[df["post"] == 1]
    cf = post[outcome] * np.exp(-beta * post["ai"] * post["sub"])
    return float((cf - post[outcome]).sum())


def extract_triple(model) -> dict:
    coefs = model.coef()
    ses = model.se()
    pvals = model.pvalue()
    ci = model.confint()
    key = "ai_post_sub"
    return {
        "beta": float(coefs[key]),
        "se": float(ses[key]),
        "p": float(pvals[key]),
        "ci_low": float(ci.loc[key, "2.5%"] if "2.5%" in ci.columns
                        else ci.loc[key, "2.5 %"]),
        "ci_high": float(ci.loc[key, "97.5%"] if "97.5%" in ci.columns
                         else ci.loc[key, "97.5 %"]),
        "n_obs": int(model._N),
    }


def build_latex_table(results: pd.DataFrame) -> str:
    lines = []
    lines.append(r"\begin{table}[ht]")
    lines.append(r"\centering")
    lines.append(r"\caption{Triple-difference (DDD) estimates across the "
                 r"observed support-post funnel. The dependent variable "
                 r"is $\log(1+Y_{twk})$ where $Y$ is the cell-level count. "
                 r"Coefficients on the triple interaction "
                 r"$\text{AI}_k \cdot \text{Post}_t \cdot \text{Sub}_k$ are "
                 r"reported, with tag-clustered standard errors in parentheses. "
                 r"Implied displacement is computed as "
                 r"$\sum_{\text{post}}(Y \cdot e^{-\hat\beta \cdot \text{AI} \cdot \text{Sub}} - Y)$.}")
    lines.append(r"\label{tab:reusable_funnel}")
    lines.append(r"\begin{tabular}{lrrrrrr}")
    lines.append(r"\toprule")
    lines.append(r"Funnel stage & $\hat\beta_{DDD}$ & SE & $p$ & "
                 r"95\% CI & N obs & Implied displaced \\")
    lines.append(r"\midrule")
    for _, r in results.iterrows():
        ci = f"[{r['ci_low']:.3f}, {r['ci_high']:.3f}]"
        lines.append(
            f"{r['label']} & {r['beta']:.4f} & ({r['se']:.4f}) & "
            f"{r['p']:.4f} & {ci} & {r['n_obs']:,} & "
            f"{r['implied_displaced']:,.0f} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


def build_coefplot(results: pd.DataFrame, dest_pdf: Path, dest_png: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=200)
    ordered = list(OUTCOMES.values())
    y_pos = np.arange(len(ordered))[::-1]
    label_to_row = {r["label"]: r for _, r in results.iterrows()}
    betas = [label_to_row[lbl]["beta"] for lbl in ordered]
    errs_low = [label_to_row[lbl]["beta"] - label_to_row[lbl]["ci_low"] for lbl in ordered]
    errs_high = [label_to_row[lbl]["ci_high"] - label_to_row[lbl]["beta"] for lbl in ordered]
    ax.errorbar(betas, y_pos, xerr=[errs_low, errs_high],
                fmt="o", color="#1a1a1a", ecolor="#1a1a1a",
                elinewidth=1.2, capsize=3, markersize=5)
    ax.axvline(0, color="#888888", linestyle="--", linewidth=0.8)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(ordered)
    ax.set_xlabel(r"DDD coefficient $\hat\beta$ on AI$\cdot$Post$\cdot$Sub (95% CI)")
    ax.set_title("Support-post funnel\n"
                 "Triple-difference effects after ChatGPT (2022-11-30)",
                 fontsize=10)
    ax.grid(axis="x", linestyle=":", linewidth=0.6, alpha=0.6)
    fig.tight_layout()
    fig.savefig(dest_pdf, bbox_inches="tight")
    fig.savefig(dest_png, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    print(f"[main] start {datetime.now().isoformat(timespec='seconds')}")
    df = prepare_panel()
    print(f"[main] panel rows: {len(df):,} | AI var: {AI_VAR}")
    rows: list[dict] = []
    for col, label in OUTCOMES.items():
        print(f"\n[main] fitting {col} ({label})...")
        m = fit_ddd(df, col)
        est = extract_triple(m)
        impl = implied_displacement(df, col, est["beta"])
        rows.append({
            "outcome": col, "label": label,
            "beta": est["beta"], "se": est["se"], "p": est["p"],
            "ci_low": est["ci_low"], "ci_high": est["ci_high"],
            "n_obs": est["n_obs"], "implied_displaced": impl,
        })
        print(f"  beta_DDD={est['beta']:.4f}  SE={est['se']:.4f}  p={est['p']:.4f}  "
              f"N={est['n_obs']:,}  implied_displaced={impl:,.0f}")

    results = pd.DataFrame(rows)
    results.to_csv(MODELS_DIR / "reusable_funnel_ddd_results.csv", index=False)
    results.to_csv(TABLES_DIR / "table_reusable_funnel.csv", index=False)
    tex = build_latex_table(results)
    (TABLES_DIR / "table_reusable_funnel.tex").write_text(tex, encoding="utf-8")
    build_coefplot(
        results,
        FIGURES_DIR / "fig_reusable_funnel_coefficients.pdf",
        FIGURES_DIR / "fig_reusable_funnel_coefficients.png",
    )

    # Baseline sanity: questions_count should match published v7 (-0.108)
    base = results[results["outcome"] == "questions_count"].iloc[0]
    print(f"\n[main] SANITY: questions_count beta = {base['beta']:.4f} "
          f"(v7 baseline: -0.108)")
    if abs(base["beta"] - (-0.108)) > 0.03:
        print("  [WARN] Difference from baseline > 0.03. Inspect.")
    else:
        print("  [OK] Within 0.03 of baseline.")
    print(f"[main] implied displacement for questions_count: "
          f"{base['implied_displaced']:,.0f} (v7 baseline: ~67,000)")
    if abs(base["implied_displaced"] - 67000) > 0.15 * 67000:
        print(f"  [WARN] Implied displacement deviates >15% from 67k baseline.")
    else:
        print("  [OK] Implied displacement within 15% of 67k baseline.")
    print(f"\n[main] done {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
