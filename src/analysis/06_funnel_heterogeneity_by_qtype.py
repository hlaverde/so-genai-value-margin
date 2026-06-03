"""
Bloque 7 opcional - Heterogeneidad del funnel por question_type.

Dentro de cada uno de los 7 question_types, sub es constante, por lo que el
DDD se simplifica a un DiD:

    log(1 + Y_{t,w,k}) = beta_k * ai_post + alpha_t + delta_w + epsilon

Para cada par (qtype, outcome) se ajusta:
    formula = "log(1+Y) ~ ai_post | tag + week_id"
    vcov    = cluster por tag

Outputs:
    outputs/models/funnel_heterogeneity_by_qtype.csv  (42 filas)
    outputs/tables/table_funnel_heterogeneity_by_qtype.{tex,csv}
    outputs/figures/fig_funnel_heterogeneity_by_qtype.{pdf,png}
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

AI_VAR = "ai_answerability_structural"

OUTCOMES: dict[str, str] = {
    "questions_count": "Questions",
    "answered_questions": "Answered",
    "accepted_answer_questions": "Accepted answer",
    "accepted_nonclosed_questions": "Accepted, not closed",
    "accepted_nonnegative_questions": "Accepted, score >= 0",
    "reusable_artifacts": "Reusable artifact",
}

QTYPE_ORDER = [
    "short_code", "how_to", "long_code", "debugging_simple",
    "other_conceptual",
    "version_environment_specific", "advanced_architecture",
]

SUB_FLAG = {qt: 1 for qt in [
    "short_code", "how_to", "long_code",
    "debugging_simple", "other_conceptual"]}
for qt in ["version_environment_specific", "advanced_architecture"]:
    SUB_FLAG[qt] = 0


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["week_id"] = df["week_start"].dt.strftime("%Y-%m-%d")
    df["ai"] = df[AI_VAR].astype(float)
    df["post"] = df["post_chatgpt"].astype(int)
    df["ai_post"] = df["ai"] * df["post"]
    return df


def fit_one(sub: pd.DataFrame, outcome: str):
    work = sub.copy()
    work["log_y"] = np.log1p(work[outcome])
    fml = "log_y ~ ai_post | tag + week_id"
    return feols(fml, data=work, vcov={"CRV1": "tag"})


def extract_key(model) -> dict:
    key = "ai_post"
    coefs = model.coef()
    ses = model.se()
    pvals = model.pvalue()
    ci = model.confint()
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


def build_latex_table(wide: pd.DataFrame) -> str:
    qtypes_order = list(wide.index)
    outcomes_order = list(OUTCOMES.values())
    lines = [r"\begin{table}[ht]", r"\centering"]
    lines.append(r"\caption{Heterogeneity of the funnel response by "
                 r"question type. Each cell reports $\hat\beta$ on "
                 r"$\text{AI}\cdot\text{Post}$ from a tag-clustered DiD "
                 r"fitted within that question type only (since "
                 r"substitutable\_type is constant within a type). "
                 r"Standard errors in parentheses. * p<0.05, ** p<0.01, "
                 r"*** p<0.001.}")
    lines.append(r"\label{tab:funnel_heterogeneity_by_qtype}")
    lines.append(r"\small")
    col_spec = "l" + "c" * len(outcomes_order)
    lines.append(r"\begin{tabular}{" + col_spec + "}")
    lines.append(r"\toprule")
    header = "Question type & " + " & ".join(
        f"\\makecell{{{lbl.replace(' ', chr(92)+chr(92))}}}" for lbl in outcomes_order
    ) + r" \\"
    lines.append(header)
    lines.append(r"\midrule")
    for qt in qtypes_order:
        cells = [qt.replace("_", "\\_") + ("$^\\dagger$" if SUB_FLAG[qt] == 0 else "")]
        for outc_label in outcomes_order:
            rec = wide.loc[qt, outc_label]
            beta = rec["beta"]
            se = rec["se"]
            p = rec["p"]
            stars = ("***" if p < 0.001 else
                     "**" if p < 0.01 else
                     "*" if p < 0.05 else "")
            cells.append(f"{beta:+.3f}{stars}\\\\({se:.3f})")
        lines.append(" & ".join(cells) + r" \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\begin{flushleft}\footnotesize $^\dagger$ "
                 r"Non-substitutable question type (control group in main DDD).")
    lines.append(r"\end{flushleft}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


def build_figure(rows_long: pd.DataFrame, dest_pdf: Path, dest_png: Path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharey=True, dpi=200)
    outcomes_list = list(OUTCOMES.keys())
    qt_order = QTYPE_ORDER
    y_pos = np.arange(len(qt_order))[::-1]
    qt_to_y = dict(zip(qt_order, y_pos))
    colors = ["#9c2a2a" if SUB_FLAG[q] == 1 else "#444466" for q in qt_order]

    for i, outc in enumerate(outcomes_list):
        ax = axes.flat[i]
        sub = rows_long[rows_long["outcome"] == outc].set_index("question_type")
        sub = sub.reindex(qt_order)
        betas = sub["beta"].values
        err_lo = sub["beta"].values - sub["ci_low"].values
        err_hi = sub["ci_high"].values - sub["beta"].values
        ax.errorbar(betas, y_pos, xerr=[err_lo, err_hi],
                    fmt="o", color="#1a1a1a", ecolor="#666666",
                    elinewidth=1.0, capsize=2.5, markersize=4)
        for j, (qt, c) in enumerate(zip(qt_order, colors)):
            ax.plot(sub.loc[qt, "beta"], y_pos[j],
                    marker="o", markersize=8, color=c,
                    markeredgecolor="black", markeredgewidth=0.5)
        ax.axvline(0, color="#888888", linestyle="--", linewidth=0.7)
        ax.set_title(OUTCOMES[outc], fontsize=10)
        ax.grid(axis="x", linestyle=":", linewidth=0.5, alpha=0.6)
        if i == 0 or i == 3:
            ax.set_yticks(y_pos)
            ax.set_yticklabels(qt_order, fontsize=9)
    for ax in axes.flat:
        ax.tick_params(axis="x", labelsize=8)
    fig.suptitle(r"Funnel heterogeneity by question type"
                 r" — $\hat\beta$ on AI$\cdot$Post (95% CI)" + "\n"
                 "Red = substitutable, dark = non-substitutable",
                 fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(dest_pdf, bbox_inches="tight")
    fig.savefig(dest_png, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    print(f"[main] start {datetime.now().isoformat(timespec='seconds')}")
    panel = prepare(pd.read_csv(PANEL))
    print(f"[main] panel rows: {len(panel):,}")

    rows: list[dict] = []
    for qt in QTYPE_ORDER:
        sub = panel[panel["question_type"] == qt].copy()
        n_cells = len(sub)
        for outc in OUTCOMES:
            m = fit_one(sub, outc)
            est = extract_key(m)
            rows.append({"question_type": qt,
                         "is_substitutable": SUB_FLAG[qt],
                         "outcome": outc, "label": OUTCOMES[outc],
                         "n_cells": n_cells, **est})
            print(f"  qt={qt:>30s} | {outc:>32s} | "
                  f"beta={est['beta']:+.4f} (SE {est['se']:.4f}, "
                  f"p={est['p']:.3g})")

    rows_long = pd.DataFrame(rows)
    rows_long.to_csv(MODELS_DIR / "funnel_heterogeneity_by_qtype.csv", index=False)
    rows_long.to_csv(TABLES_DIR / "table_funnel_heterogeneity_by_qtype.csv",
                     index=False)

    # Wide pivot: rows=qtype, cols=outcome label, value=dict-of-stats
    wide_struct: dict = {}
    for qt in QTYPE_ORDER:
        wide_struct[qt] = {}
        for outc in OUTCOMES:
            row = rows_long[(rows_long["question_type"] == qt)
                            & (rows_long["outcome"] == outc)].iloc[0]
            wide_struct[qt][OUTCOMES[outc]] = {
                "beta": row["beta"], "se": row["se"], "p": row["p"],
            }
    wide_df = pd.DataFrame.from_dict(wide_struct, orient="index")
    (TABLES_DIR / "table_funnel_heterogeneity_by_qtype.tex").write_text(
        build_latex_table(wide_df), encoding="utf-8")

    build_figure(rows_long,
                 FIGURES_DIR / "fig_funnel_heterogeneity_by_qtype.pdf",
                 FIGURES_DIR / "fig_funnel_heterogeneity_by_qtype.png")

    print(f"\n[main] done {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
