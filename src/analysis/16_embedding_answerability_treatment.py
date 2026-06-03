"""Estimate the DDD using embedding-based AI-answerability as treatment.

The baseline paper uses a pre-treatment structural tag-level proxy for
AI-answerability. This script addresses the construct-validity concern
that the structural proxy may mix answerability with popularity or tag
maturity by re-estimating the main DDD with the independently generated
embedding-based tag score from ``12_ai_answerability_embedding_validation``.

Outputs:
    outputs/models/embedding_answerability_treatment_ddd.csv
    outputs/tables/table_embedding_answerability_treatment.tex
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pyfixest.estimation import feols

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.paths import OUTPUTS_DIR, PROCESSED_DIR  # noqa: E402

PANEL_PATH = PROCESSED_DIR / "stackoverflow_question_type_master_panel.csv"
EMBED_TAG_PATH = OUTPUTS_DIR / "models" / "embedding_validation_tag_scores.csv"
MODELS_DIR = OUTPUTS_DIR / "models"
TABLES_DIR = OUTPUTS_DIR / "tables"
CHATGPT_CUTOFF = pd.Timestamp("2022-11-30")

for _d in (MODELS_DIR, TABLES_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def fit_ddd(panel: pd.DataFrame, ai_col: str) -> dict[str, float | int | str]:
    work = panel.copy()
    work["week_start"] = pd.to_datetime(work["week_start"], errors="coerce")
    work["week_id"] = work["week_start"].dt.strftime("%Y-%m-%d")
    work["post"] = (work["week_start"] >= CHATGPT_CUTOFF).astype(int)
    work["sub"] = work["substitutable_type"].astype(int)
    work["ai"] = work[ai_col].astype(float)
    work["ai_post"] = work["ai"] * work["post"]
    work["ai_sub"] = work["ai"] * work["sub"]
    work["post_sub"] = work["post"] * work["sub"]
    work["ai_post_sub"] = work["ai"] * work["post"] * work["sub"]
    work["log_y"] = np.log1p(work["questions"])
    formula = "log_y ~ ai_post + ai_sub + post_sub + ai_post_sub | tag_qtype + week_id"
    model = feols(formula, data=work, vcov={"CRV1": "tag"})
    key = "ai_post_sub"
    return {
        "ai_measure": ai_col,
        "beta": float(model.coef()[key]),
        "se": float(model.se()[key]),
        "p": float(model.pvalue()[key]),
        "n_obs": int(model._N),
        "n_tags": int(work["tag"].nunique()),
    }


def build_latex(results: pd.DataFrame) -> str:
    nice = {
        "ai_answerability_structural": "Structural proxy",
        "embed_answerability_z": "Embedding answerability (z)",
    }
    lines = [
        r"\begin{table}[ht]",
        r"\centering",
        r"\caption{DDD estimates using alternative tag-level treatment measures. "
        r"The embedding-answerability treatment is the tag-level mean cosine-similarity "
        r"differential from Table~\ref{tab:embedding_validation}, standardized to mean "
        r"zero and unit variance across the 100 tags. It is independent of the "
        r"historical Stack Overflow features used in the structural proxy.}",
        r"\label{tab:embedding_answerability_treatment}",
        r"\small",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Treatment measure & $\hat\beta_{DDD}$ & SE & $p$ & N \\",
        r"\midrule",
    ]
    for _, row in results.iterrows():
        stars = "***" if row["p"] < 0.01 else "**" if row["p"] < 0.05 else "*" if row["p"] < 0.1 else ""
        lines.append(
            f"{nice.get(row['ai_measure'], row['ai_measure'])} & "
            f"{row['beta']:.4f}{stars} & {row['se']:.4f} & "
            f"{row['p']:.4f} & {int(row['n_obs']):,} \\\\"
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\begin{minipage}{0.92\textwidth}",
            r"\scriptsize Notes. Outcome is $\log(1+\text{questions})$ at the "
            r"tag-week-question-type level. All specifications include "
            r"tag$\times$question-type and week fixed effects and cluster standard "
            r"errors by tag. The embedding treatment is a measurement check, not a "
            r"frontier-LLM benchmark.",
            r"\end{minipage}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    panel = pd.read_csv(PANEL_PATH)
    embed = pd.read_csv(EMBED_TAG_PATH)[["tag", "embed_answerability_mean"]]
    embed["embed_answerability_z"] = (
        embed["embed_answerability_mean"] - embed["embed_answerability_mean"].mean()
    ) / embed["embed_answerability_mean"].std(ddof=0)
    panel = panel.merge(embed[["tag", "embed_answerability_z"]], on="tag", how="inner", validate="m:1")

    rows = [
        fit_ddd(panel, "ai_answerability_structural"),
        fit_ddd(panel, "embed_answerability_z"),
    ]
    results = pd.DataFrame(rows)
    results.to_csv(MODELS_DIR / "embedding_answerability_treatment_ddd.csv", index=False)
    (TABLES_DIR / "table_embedding_answerability_treatment.tex").write_text(
        build_latex(results),
        encoding="utf-8",
    )
    print(results.to_string(index=False))


if __name__ == "__main__":
    main()
