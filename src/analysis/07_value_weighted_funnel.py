"""
Extension - Value-weighted funnel-qualified posts.

Recommended by adversarial DSS review: distinguish counts from value.

Outcomes added beyond the count-based funnel:
    high_value_artifact   = accepted & (is_closed==0) & (score >= 1)
    very_high_value       = accepted & (is_closed==0) & (score >= 5)
    value_weighted        = sum over questions of (curated_flag * log1p(max(score,0)))

Each panel cell gets a count of high-value and very-high-value artefacts,
and a value-weighted sum. Then we run the same DDD specification on the
log1p of each new outcome.

Outputs:
    data/processed/value_weighted_funnel_panel.csv
    outputs/models/value_weighted_funnel_ddd_results.csv
    outputs/tables/table_value_weighted_funnel.{tex,csv}
    outputs/figures/fig_value_weighted_funnel.{pdf,png}
    outputs/diagnostics/value_weighted_funnel_build_audit.md
"""
from __future__ import annotations

import sys
import time
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

from src.paths import OUTPUTS_DIR, PROCESSED_DIR, RAW_DIR  # noqa: E402
from src.data.prepare_stackoverflow_question_type_raw import (  # noqa: E402
    TAG_ALIASES,
    classify_questions,
    source_files,
)

CUTOFF = pd.Timestamp("2022-11-30")
PANEL_WEEK_MIN = pd.Timestamp("2020-01-06")
RAW_SO_DIR = RAW_DIR / "stackoverflow"

OUTPUT_PANEL = PROCESSED_DIR / "value_weighted_funnel_panel.csv"
AUDIT = OUTPUTS_DIR / "diagnostics" / "value_weighted_funnel_build_audit.md"
AI_ANSWERABILITY = PROCESSED_DIR / "ai_answerability_real.csv"
MODELS_DIR = OUTPUTS_DIR / "models"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"
for _d in (MODELS_DIR, TABLES_DIR, FIGURES_DIR, AUDIT.parent):
    _d.mkdir(parents=True, exist_ok=True)

USECOLS = [
    "tag", "week_start", "question_id", "owner_user_id",
    "title", "body_length", "has_code",
    "score", "answer_count", "has_accepted_answer", "is_closed",
]
NUMERIC_COLS = [
    "question_id", "owner_user_id", "body_length",
    "has_code", "score", "answer_count",
    "has_accepted_answer", "is_closed",
]
GROUP_KEYS = ["tag", "week_start", "question_type", "substitutable_type"]

AI_VAR = "ai_answerability_structural"

OUTCOMES_NEW: dict[str, str] = {
    "curated_artefacts": "Funnel-qualified post (count, baseline)",
    "high_value_artifacts": "High-value (score $\\geq 1$)",
    "very_high_value_artifacts": "Very-high-value (score $\\geq 5$)",
    "value_weighted_artifacts": "Value-weighted ($\\log(1+\\max(s,0))$)",
}


def load_raw_all(files: list[Path]) -> tuple[pd.DataFrame, dict]:
    t0 = time.perf_counter()
    frames: list[pd.DataFrame] = []
    for i, path in enumerate(files, start=1):
        frames.append(pd.read_csv(path, usecols=USECOLS))
        if i % 100 == 0 or i == len(files):
            print(f"  ... {i}/{len(files)} files read")
    raw = pd.concat(frames, ignore_index=True)
    del frames
    raw["tag"] = raw["tag"].replace(TAG_ALIASES)
    raw = raw.drop_duplicates(["question_id", "tag"]).reset_index(drop=True)
    raw["week_start"] = pd.to_datetime(raw["week_start"], errors="coerce")
    for col in NUMERIC_COLS:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    audit = {
        "files_loaded": len(files),
        "rows": len(raw),
        "load_elapsed_s": round(time.perf_counter() - t0, 1),
    }
    print(f"[load_raw_all] {audit}")
    return raw, audit


def add_value_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    acc = (df["has_accepted_answer"].fillna(0) == 1)
    closed = (df["is_closed"].fillna(0) == 1)
    score = df["score"].fillna(0)
    df["curated"] = (acc & ~closed & (score >= 0)).astype("int8")
    df["high_value"] = (acc & ~closed & (score >= 1)).astype("int8")
    df["very_high_value"] = (acc & ~closed & (score >= 5)).astype("int8")
    # Value weight: only counted when curated; weight = log(1 + max(score,0))
    df["value_weight"] = (
        df["curated"].astype(float) * np.log1p(np.clip(score, 0, None))
    )
    return df


def aggregate_value_panel(df: pd.DataFrame) -> pd.DataFrame:
    panel = (
        df.groupby(GROUP_KEYS, dropna=False)
        .agg(
            questions_count=("question_id", "nunique"),
            curated_artefacts=("curated", "sum"),
            high_value_artifacts=("high_value", "sum"),
            very_high_value_artifacts=("very_high_value", "sum"),
            value_weighted_artifacts=("value_weight", "sum"),
        )
        .reset_index()
    )
    panel = panel.sort_values(GROUP_KEYS).reset_index(drop=True)
    panel["week_start"] = pd.to_datetime(panel["week_start"], errors="coerce")
    panel = panel[panel["week_start"] >= PANEL_WEEK_MIN].reset_index(drop=True)
    return panel


def merge_answerability(panel: pd.DataFrame) -> pd.DataFrame:
    ai = pd.read_csv(AI_ANSWERABILITY)
    keep = [
        "tag",
        "ai_answerability_zscore",
        "ai_answerability_pca",
        "ai_answerability_quantile",
        "ai_answerability_structural",
    ]
    ai = ai[keep]
    return panel.merge(ai, on="tag", how="left", validate="m:1")


def add_post(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    wk = pd.to_datetime(panel["week_start"], errors="coerce")
    panel["post_chatgpt"] = (wk >= CUTOFF).astype("int8")
    return panel


def fit_ddd(panel: pd.DataFrame, outcome: str):
    work = panel.copy()
    work["tag_qtype"] = work["tag"].astype(str) + "::" + work["question_type"].astype(str)
    work["week_id"] = work["week_start"].dt.strftime("%Y-%m-%d")
    work["ai"] = work[AI_VAR].astype(float)
    work["post"] = work["post_chatgpt"].astype(int)
    work["sub"] = work["substitutable_type"].astype(int)
    work["ai_post"] = work["ai"] * work["post"]
    work["ai_sub"] = work["ai"] * work["sub"]
    work["post_sub"] = work["post"] * work["sub"]
    work["ai_post_sub"] = work["ai"] * work["post"] * work["sub"]
    work["log_y"] = np.log1p(work[outcome])
    fml = "log_y ~ ai_post + ai_sub + post_sub + ai_post_sub | tag_qtype + week_id"
    return feols(fml, data=work, vcov={"CRV1": "tag"})


def implied_displacement(panel: pd.DataFrame, outcome: str, beta: float) -> float:
    work = panel.copy()
    work["ai"] = work[AI_VAR].astype(float)
    work["post"] = work["post_chatgpt"].astype(int)
    work["sub"] = work["substitutable_type"].astype(int)
    post = work[work["post"] == 1]
    cf = post[outcome] * np.exp(-beta * post["ai"] * post["sub"])
    return float((cf - post[outcome]).sum())


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


def build_latex(results: pd.DataFrame) -> str:
    lines = [
        r"\begin{table}[ht]", r"\centering",
        r"\caption{Value-weighted funnel-qualified-post outcomes. "
        r"Counts only accepted, non-closed posts that meet successively stricter "
        r"value thresholds, and a value-weighted aggregate. "
        r"Each row is a DDD on $\log(1+Y_{twk})$ for the new "
        r"outcome $Y$. Implied displacement computed cell by cell.}",
        r"\label{tab:value_weighted_funnel}",
        r"\small \setlength{\tabcolsep}{4pt}",
        r"\begin{adjustbox}{max width=\textwidth}",
        r"\begin{tabular}{lrrrrrr}",
        r"\toprule",
        r"Outcome & $\hat\beta_{DDD}$ & SE & $p$ & 95\% CI & N obs & Implied displaced \\",
        r"\midrule",
    ]
    for _, r in results.iterrows():
        ci = f"[{r['ci_low']:.3f}, {r['ci_high']:.3f}]"
        impl_str = (f"{r['implied_displaced']:,.0f}"
                    if abs(r["implied_displaced"]) >= 10
                    else f"{r['implied_displaced']:.2f}")
        lines.append(
            f"{r['label']} & {r['beta']:.4f} & ({r['se']:.4f}) & "
            f"{r['p']:.4f} & {ci} & {r['n_obs']:,} & {impl_str} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{adjustbox}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


def build_figure(results: pd.DataFrame, dest_pdf: Path, dest_png: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.8, 4.0), dpi=200)
    labels = list(results["label"])
    y_pos = np.arange(len(labels))[::-1]
    betas = results["beta"].values
    errs_low = betas - results["ci_low"].values
    errs_high = results["ci_high"].values - betas
    ax.errorbar(betas, y_pos, xerr=[errs_low, errs_high],
                fmt="o", color="#1a1a1a", ecolor="#1a1a1a",
                elinewidth=1.2, capsize=3, markersize=5)
    ax.axvline(0, color="#888888", linestyle="--", linewidth=0.8)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel(r"DDD coefficient $\hat\beta$ on AI$\cdot$Post$\cdot$Sub (95% CI)")
    ax.set_title("Value-weighted funnel-qualified posts\n"
                 "DDD effect by post value threshold",
                 fontsize=10)
    ax.grid(axis="x", linestyle=":", linewidth=0.6, alpha=0.6)
    fig.tight_layout()
    fig.savefig(dest_pdf, bbox_inches="tight")
    fig.savefig(dest_png, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    print(f"[main] start {datetime.now().isoformat(timespec='seconds')}")
    files = source_files(RAW_SO_DIR, year=None)
    raw, load_audit = load_raw_all(files)
    print("[main] classifying ...")
    raw = classify_questions(raw)
    print("[main] adding value flags ...")
    raw = add_value_flags(raw)
    print("[main] aggregating panel ...")
    panel = aggregate_value_panel(raw)
    del raw
    panel = merge_answerability(panel)
    panel = add_post(panel)
    panel.to_csv(OUTPUT_PANEL, index=False)
    print(f"[main] wrote {OUTPUT_PANEL} ({OUTPUT_PANEL.stat().st_size/1e6:.1f} MB)")

    # Global summary
    totals = {
        "curated": int(panel["curated_artefacts"].sum()),
        "high_value": int(panel["high_value_artifacts"].sum()),
        "very_high_value": int(panel["very_high_value_artifacts"].sum()),
        "value_weighted_sum": float(panel["value_weighted_artifacts"].sum()),
    }
    print(f"[main] global sums: {totals}")

    rows = []
    for col, label in OUTCOMES_NEW.items():
        print(f"\n[main] fitting {col} ({label})...")
        m = fit_ddd(panel, col)
        est = extract_triple(m)
        impl = implied_displacement(panel, col, est["beta"])
        rows.append({"outcome": col, "label": label, **est,
                     "implied_displaced": impl})
        print(f"  beta_DDD={est['beta']:.4f}  SE={est['se']:.4f}  "
              f"p={est['p']:.4f}  implied={impl:,.2f}")

    results = pd.DataFrame(rows)
    results.to_csv(MODELS_DIR / "value_weighted_funnel_ddd_results.csv", index=False)
    results.to_csv(TABLES_DIR / "table_value_weighted_funnel.csv", index=False)
    (TABLES_DIR / "table_value_weighted_funnel.tex").write_text(
        build_latex(results), encoding="utf-8")
    build_figure(
        results,
        FIGURES_DIR / "fig_value_weighted_funnel.pdf",
        FIGURES_DIR / "fig_value_weighted_funnel.png",
    )

    # Audit
    lines = ["# Value-Weighted Funnel-Qualified Post Audit",
             f"\n_Generated: {datetime.now().isoformat(timespec='seconds')}_\n",
             "## Global totals\n"]
    for k, v in totals.items():
        lines.append(f"- **{k}**: {v:,}" if isinstance(v, int) else f"- **{k}**: {v:,.0f}")
    lines.append("\n## DDD results\n")
    for _, r in results.iterrows():
        lines.append(
            f"- **{r['outcome']}**: beta={r['beta']:.4f}, "
            f"SE={r['se']:.4f}, p={r['p']:.4f}, "
            f"implied_displaced={r['implied_displaced']:,.2f}")
    AUDIT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[main] audit written to {AUDIT}")
    print(f"[main] done {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
