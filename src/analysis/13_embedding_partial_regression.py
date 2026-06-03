"""
Partial-regression validation: does the embedding-based score still
correlate with the structural AI-answerability index after controlling
for tag-level popularity, maturity, and accepted-answer rate?

Referee 2 worry: the positive correlation between the embedding score
and the structural proxy could be a popularity artefact.  We control
for log(pre-volume), tag maturity, and pre-period accepted-answer rate
and test whether the partial coefficient survives.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.paths import OUTPUTS_DIR, PROCESSED_DIR  # noqa: E402

MODELS_DIR = OUTPUTS_DIR / "models"
TABLES_DIR = OUTPUTS_DIR / "tables"

EMBED = MODELS_DIR / "embedding_validation_tag_scores.csv"
AI = PROCESSED_DIR / "ai_answerability_real.csv"


def main():
    print(f"[main] start {datetime.now().isoformat(timespec='seconds')}")
    emb = pd.read_csv(EMBED)
    ai = pd.read_csv(AI)

    # Merge tag-level controls
    df = emb.merge(
        ai[["tag", "questions_pre", "tag_maturity_weeks_pre",
            "accepted_answer_rate_pre"]],
        on="tag", how="inner",
    )
    df["log_pre_volume"] = np.log1p(df["questions_pre"])
    print(f"[main] {len(df)} tags after merge")
    print(df.describe().T[["mean", "std", "min", "max"]].round(3))

    # Run four regressions of embedding score on structural proxy,
    # progressively adding controls
    y = df["embed_answerability_mean"]

    def fit_and_summarise(X_cols, label):
        X = sm.add_constant(df[X_cols])
        m = sm.OLS(y, X, missing="drop").fit(
            cov_type="HC1")
        coef = m.params["ai_answerability_structural"]
        se = m.bse["ai_answerability_structural"]
        p = m.pvalues["ai_answerability_structural"]
        return {
            "spec": label,
            "controls": ", ".join([c for c in X_cols
                                   if c != "ai_answerability_structural"]) or "none",
            "ai_proxy_coef": float(coef),
            "ai_proxy_se": float(se),
            "ai_proxy_p": float(p),
            "ai_proxy_t": float(coef / se),
            "r2": float(m.rsquared),
            "n_tags": int(m.nobs),
        }

    specs = []
    specs.append(fit_and_summarise(
        ["ai_answerability_structural"],
        "(1) bivariate"))
    specs.append(fit_and_summarise(
        ["ai_answerability_structural", "log_pre_volume"],
        "(2) + log(pre-volume)"))
    specs.append(fit_and_summarise(
        ["ai_answerability_structural", "log_pre_volume",
         "tag_maturity_weeks_pre"],
        "(3) + maturity"))
    specs.append(fit_and_summarise(
        ["ai_answerability_structural", "log_pre_volume",
         "tag_maturity_weeks_pre", "accepted_answer_rate_pre"],
        "(4) + accepted rate"))

    out = pd.DataFrame(specs)
    print("\n[main] Partial-regression results:")
    print(out.to_string(index=False))

    out.to_csv(MODELS_DIR / "embedding_partial_regression.csv", index=False)

    # LaTeX
    lines = [
        r"\begin{table}[ht]", r"\centering",
        r"\caption{Partial-regression test for the embedding-based "
        r"validation of the AI-answerability proxy. Each row reports "
        r"the OLS coefficient of the embedding-based score on the "
        r"\texttt{ai\_answerability\_structural} proxy, adding "
        r"tag-level controls progressively: $\log(1+\text{pre-period}~"
        r"\text{questions})$, tag maturity (weeks since first "
        r"appearance), and pre-ChatGPT accepted-answer rate. A "
        r"positive coefficient that survives the addition of "
        r"popularity-, maturity-, and accepted-rate controls "
        r"indicates that the embedding-based validation does not "
        r"merely capture historical popularity. Standard errors are "
        r"$\text{HC1}$-robust.}",
        r"\label{tab:embedding_partial_regression}",
        r"\small",
        r"\begin{tabular}{llrrrrr}",
        r"\toprule",
        r"Specification & Controls & Coef. & SE & $t$ & $p$ & $R^2$ \\",
        r"\midrule",
    ]
    for _, r in out.iterrows():
        lines.append(
            f"{r['spec']} & {r['controls']} & {r['ai_proxy_coef']:.4f} & "
            f"{r['ai_proxy_se']:.4f} & {r['ai_proxy_t']:.2f} & "
            f"{r['ai_proxy_p']:.4f} & {r['r2']:.3f} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    (TABLES_DIR / "table_embedding_partial_regression.tex").write_text(
        "\n".join(lines), encoding="utf-8")
    print(f"saved {TABLES_DIR / 'table_embedding_partial_regression.tex'}")

    print(f"\n[main] done {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
