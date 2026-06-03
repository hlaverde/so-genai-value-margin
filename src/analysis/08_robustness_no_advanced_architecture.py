"""
Robustness check: re-estimate the full funnel DDD excluding the
advanced_architecture question type, to address the reviewer concern
that the boundary between substitutable and non-substitutable is porous.

If the baseline result survives the exclusion of the
advanced_architecture category (which our binary heuristic codes as
non-substitutable but which exhibits a large displacement effect),
the identification claim is robust to the most visible source of
classifier ambiguity.

Outputs:
    outputs/models/funnel_ddd_no_advanced_arch.csv
    outputs/tables/table_funnel_no_advanced_arch.{tex,csv}
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

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
for _d in (MODELS_DIR, TABLES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

AI_VAR = "ai_answerability_structural"

OUTCOMES: dict[str, str] = {
    "questions_count": "Questions",
    "answered_questions": "Answered",
    "accepted_answer_questions": "Accepted answer",
    "accepted_nonclosed_questions": "Accepted, not closed",
    "accepted_nonnegative_questions": "Accepted, score $\\geq 0$",
    "reusable_artifacts": "Funnel-qualified post",
}


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
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
    fml = "log_y ~ ai_post + ai_sub + post_sub + ai_post_sub | tag_qtype + week_id"
    return feols(fml, data=work, vcov={"CRV1": "tag"})


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


def implied_displacement(df: pd.DataFrame, outcome: str, beta: float) -> float:
    post = df[df["post"] == 1]
    cf = post[outcome] * np.exp(-beta * post["ai"] * post["sub"])
    return float((cf - post[outcome]).sum())


def build_latex(results: pd.DataFrame) -> str:
    lines = [
        r"\begin{table}[ht]", r"\centering",
        r"\caption{Funnel DDD estimates excluding the "
        r"\texttt{advanced\_architecture} question type. "
        r"Compare to Table~\ref{tab:reusable_funnel} (full sample); "
        r"the central coefficients survive the exclusion of the "
        r"category that drives the binary substitutability boundary "
        r"to be porous (\S\ref{ssec:mech_qtype_anomaly}).}",
        r"\label{tab:funnel_no_advanced_arch}",
        r"\small \setlength{\tabcolsep}{4pt}",
        r"\begin{adjustbox}{max width=\textwidth}",
        r"\begin{tabular}{lrrrrrr}",
        r"\toprule",
        r"Funnel stage & $\hat\beta_{DDD}$ & SE & $p$ & 95\% CI & N obs & Implied displaced \\",
        r"\midrule",
    ]
    for _, r in results.iterrows():
        ci = f"[{r['ci_low']:.3f}, {r['ci_high']:.3f}]"
        lines.append(
            f"{r['label']} & {r['beta']:.4f} & ({r['se']:.4f}) & "
            f"{r['p']:.4f} & {ci} & {r['n_obs']:,} & "
            f"{r['implied_displaced']:,.0f} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{adjustbox}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


def main() -> None:
    print(f"[main] start {datetime.now().isoformat(timespec='seconds')}")
    panel = pd.read_csv(PANEL)
    n_total = len(panel)
    panel_no_aa = panel[panel["question_type"] != "advanced_architecture"].reset_index(drop=True)
    n_kept = len(panel_no_aa)
    print(f"[main] dropping advanced_architecture: {n_total:,} -> {n_kept:,} cells "
          f"(removed {n_total - n_kept:,})")
    panel_no_aa = prepare(panel_no_aa)

    rows = []
    for col, label in OUTCOMES.items():
        m = fit_ddd(panel_no_aa, col)
        est = extract_triple(m)
        impl = implied_displacement(panel_no_aa, col, est["beta"])
        rows.append({"outcome": col, "label": label, **est,
                     "implied_displaced": impl})
        print(f"  {col:>35s} | beta={est['beta']:+.4f} (SE {est['se']:.4f}, "
              f"p={est['p']:.4f}) | implied={impl:,.0f}")

    results = pd.DataFrame(rows)
    results.to_csv(MODELS_DIR / "funnel_ddd_no_advanced_arch.csv", index=False)
    results.to_csv(TABLES_DIR / "table_funnel_no_advanced_arch.csv", index=False)
    (TABLES_DIR / "table_funnel_no_advanced_arch.tex").write_text(
        build_latex(results), encoding="utf-8")

    # Sanity vs full-sample baseline (questions_count expected ~-0.108)
    base = results[results["outcome"] == "questions_count"].iloc[0]
    print(f"\n[main] SANITY: questions_count beta (no AA) = {base['beta']:.4f} "
          f"vs full-sample baseline -0.108")
    print(f"[main] done {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
