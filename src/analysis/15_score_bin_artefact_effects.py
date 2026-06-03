"""Estimate DDD effects by mutually exclusive score bins.

This answers a referee concern that threshold outcomes (score >= 1,
score >= 5) can hide where in the score distribution displacement occurs.
Bins are mutually exclusive: score = 0, 1, 2, 3, 4, and >= 5.

Outputs:
    data/processed/score_bin_artefact_panel.csv
    outputs/models/score_bin_artefact_effects.csv
    outputs/tables/table_score_bin_artefact_effects.{csv,tex}
    outputs/figures/fig_score_bin_artefact_effects.{pdf,png}
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

from src.data.prepare_stackoverflow_question_type_raw import (  # noqa: E402
    TAG_ALIASES,
    classify_questions,
    source_files,
)
from src.paths import OUTPUTS_DIR, PROCESSED_DIR, RAW_DIR  # noqa: E402

CUTOFF = pd.Timestamp("2022-11-30")
PANEL_WEEK_MIN = pd.Timestamp("2020-01-06")
RAW_SO_DIR = RAW_DIR / "stackoverflow"
AI_ANSWERABILITY = PROCESSED_DIR / "ai_answerability_real.csv"
OUTPUT_PANEL = PROCESSED_DIR / "score_bin_artefact_panel.csv"
MODELS_DIR = OUTPUTS_DIR / "models"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"

for _d in (MODELS_DIR, TABLES_DIR, FIGURES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

AI_VAR = "ai_answerability_structural"
USECOLS = [
    "tag",
    "week_start",
    "question_id",
    "title",
    "body_length",
    "has_code",
    "score",
    "has_accepted_answer",
    "is_closed",
]
NUMERIC_COLS = [
    "question_id",
    "body_length",
    "has_code",
    "score",
    "has_accepted_answer",
    "is_closed",
]
GROUP_KEYS = ["tag", "week_start", "question_type", "substitutable_type"]
BIN_LABELS = {
    "score_eq_0": "score = 0",
    "score_eq_1": "score = 1",
    "score_eq_2": "score = 2",
    "score_eq_3": "score = 3",
    "score_eq_4": "score = 4",
    "score_ge_5": r"score $\geq$ 5",
}


def load_raw_all() -> pd.DataFrame:
    t0 = time.perf_counter()
    files = source_files(RAW_SO_DIR, year=None)
    frames = []
    print(f"[load] reading {len(files)} raw files")
    for i, path in enumerate(files, start=1):
        frames.append(pd.read_csv(path, usecols=USECOLS))
        if i % 100 == 0 or i == len(files):
            print(f"  ... {i}/{len(files)}")
    raw = pd.concat(frames, ignore_index=True)
    raw["tag"] = raw["tag"].replace(TAG_ALIASES)
    raw = raw.drop_duplicates(["question_id", "tag"]).reset_index(drop=True)
    raw["week_start"] = pd.to_datetime(raw["week_start"], errors="coerce")
    for col in NUMERIC_COLS:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    raw = raw[raw["week_start"] >= PANEL_WEEK_MIN].reset_index(drop=True)
    print(f"[load] rows={len(raw):,}; elapsed={time.perf_counter() - t0:.1f}s")
    return raw


def build_panel(raw: pd.DataFrame) -> pd.DataFrame:
    df = classify_questions(raw)
    score = df["score"].fillna(0).astype(float)
    curated = (df["has_accepted_answer"].fillna(0).eq(1)) & (
        df["is_closed"].fillna(0).eq(0)
    )

    df["score_eq_0"] = (curated & score.eq(0)).astype("int8")
    df["score_eq_1"] = (curated & score.eq(1)).astype("int8")
    df["score_eq_2"] = (curated & score.eq(2)).astype("int8")
    df["score_eq_3"] = (curated & score.eq(3)).astype("int8")
    df["score_eq_4"] = (curated & score.eq(4)).astype("int8")
    df["score_ge_5"] = (curated & score.ge(5)).astype("int8")

    panel = (
        df.groupby(GROUP_KEYS, dropna=False)
        .agg(**{col: (col, "sum") for col in BIN_LABELS})
        .reset_index()
    )
    panel["week_start"] = pd.to_datetime(panel["week_start"], errors="coerce")

    ai = pd.read_csv(AI_ANSWERABILITY)[["tag", AI_VAR]]
    panel = panel.merge(ai, on="tag", how="left", validate="m:1")
    panel["post_chatgpt"] = (panel["week_start"] >= CUTOFF).astype("int8")
    panel = panel.sort_values(GROUP_KEYS).reset_index(drop=True)
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
    formula = "log_y ~ ai_post + ai_sub + post_sub + ai_post_sub | tag_qtype + week_id"
    return feols(formula, data=work, vcov={"CRV1": "tag"})


def extract_triple(model) -> dict[str, float | int]:
    key = "ai_post_sub"
    ci = model.confint()
    low_col = "2.5%" if "2.5%" in ci.columns else "2.5 %"
    high_col = "97.5%" if "97.5%" in ci.columns else "97.5 %"
    se = float(model.se()[key])
    return {
        "beta": float(model.coef()[key]),
        "se": se,
        "p": float(model.pvalue()[key]),
        "ci_low": float(ci.loc[key, low_col]),
        "ci_high": float(ci.loc[key, high_col]),
        # Two-sided alpha=.05, 80% power: z(.975)+z(.80) ~= 1.96+0.84.
        # This is an approximation because the model uses clustered FE
        # inference; it is intended as a transparent power diagnostic.
        "mde_80": 2.80 * se,
        "n_obs": int(model._N),
    }


def build_latex(results: pd.DataFrame) -> str:
    lines = [
        r"\begin{table}[ht]",
        r"\centering",
        r"\caption{Mutually exclusive score-bin effects for accepted, non-closed posts. "
        r"Each row re-fits the baseline DDD with the dependent variable equal "
        r"to the count of posts in the score bin. "
        r"Unlike cumulative threshold outcomes, these bins show where in the "
        r"crowd-score distribution the negative association is concentrated. "
        r"The MDE column reports the approximate two-sided 5\% test, "
        r"80\% power minimum detectable effect, computed as $2.80\times SE$.}",
        r"\label{tab:score_bin_artefact_effects}",
        r"\small",
        r"\begin{tabular}{lrrrrrrr}",
        r"\toprule",
        r"Score bin & $\hat\beta_{DDD}$ & SE & MDE$_{80}$ & $p$ & 95\% CI & N obs & $N$ posts \\",
        r"\midrule",
    ]
    for _, row in results.iterrows():
        ci = f"[{row['ci_low']:.3f}, {row['ci_high']:.3f}]"
        lines.append(
            f"{row['label']} & {row['beta']:.4f} & {row['se']:.4f} & "
            f"{row['mde_80']:.3f} & {row['p']:.4f} & {ci} & {int(row['n_obs']):,} & "
            f"{int(row['n_artefacts']):,} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    return "\n".join(lines)


def build_figure(results: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 3.9), dpi=200)
    x = np.arange(len(results))
    beta = results["beta"].to_numpy()
    yerr = np.vstack([beta - results["ci_low"], results["ci_high"] - beta])
    colors = ["#555555" if p >= 0.05 else "#b33a3a" for p in results["p"]]
    ax.errorbar(x, beta, yerr=yerr, fmt="none", ecolor="#222222", capsize=3, lw=1)
    ax.scatter(x, beta, s=42, c=colors, zorder=3)
    ax.axhline(0, color="#777777", linestyle="--", linewidth=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(results["label"], rotation=0)
    ax.set_ylabel(r"DDD coefficient $\hat\beta$")
    ax.set_title("Accepted non-closed posts by mutually exclusive score bin")
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.65)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_score_bin_artefact_effects.pdf", bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig_score_bin_artefact_effects.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    print(f"[main] start {datetime.now().isoformat(timespec='seconds')}")
    raw = load_raw_all()
    panel = build_panel(raw)
    panel.to_csv(OUTPUT_PANEL, index=False)
    print(f"[panel] wrote {OUTPUT_PANEL} rows={len(panel):,}")

    rows = []
    for outcome, label in BIN_LABELS.items():
        model = fit_ddd(panel, outcome)
        est = extract_triple(model)
        n_artefacts = int(panel[outcome].sum())
        rows.append(
            {
                "outcome": outcome,
                "label": label,
                **est,
                "n_artefacts": n_artefacts,
            }
        )
        print(
            f"[fit] {label}: beta={est['beta']:.4f}, se={est['se']:.4f}, "
            f"p={est['p']:.4f}, artefacts={n_artefacts:,}"
        )

    results = pd.DataFrame(rows)
    results.to_csv(MODELS_DIR / "score_bin_artefact_effects.csv", index=False)
    results.to_csv(TABLES_DIR / "table_score_bin_artefact_effects.csv", index=False)
    (TABLES_DIR / "table_score_bin_artefact_effects.tex").write_text(
        build_latex(results),
        encoding="utf-8",
    )
    build_figure(results)
    print(f"[main] done {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
