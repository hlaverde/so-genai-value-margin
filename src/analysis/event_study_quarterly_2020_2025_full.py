"""Quarterly DDD event study extended through Q4 2025."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyfixest as pf

THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.paths import FIGURES_DIR, PROCESSED_DIR, TABLES_DIR  # noqa: E402

CHATGPT_RELEASE = pd.Timestamp("2022-11-30")
BIN_WEEKS = 13


def event_bin(week: pd.Timestamp) -> int:
    return ((week - CHATGPT_RELEASE).days // 7) // BIN_WEEKS


def bin_period(df: pd.DataFrame, b: int) -> str:
    s = df.loc[df["event_bin"] == b, "week_start"]
    return f"{s.min():%Y-%m-%d} to {s.max():%Y-%m-%d}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=PROCESSED_DIR / "panel_tag_week_question_type_2020_2025.csv")
    parser.add_argument("--answerability", default="ai_answerability_structural")
    parser.add_argument("--table", type=Path, default=TABLES_DIR / "event_study_quarterly_2020_2025_full.csv")
    parser.add_argument("--figure", type=Path, default=FIGURES_DIR / "event_study_quarterly_2020_2025_full.pdf")
    args = parser.parse_args()
    df = pd.read_csv(args.panel)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df = df[df["week_start"].dt.year <= 2025].copy()
    df["sub"] = pd.to_numeric(df["substitutable_type"], errors="coerce").fillna(0).astype(int)
    df["ai_sub"] = pd.to_numeric(df[args.answerability], errors="coerce") * df["sub"]
    df["event_bin"] = df["week_start"].apply(event_bin)
    df["week_id"] = df["week_start"].dt.strftime("%Y-%m-%d")
    df["tag_qtype"] = df["tag"].astype(str) + "::" + df["question_type"].astype(str)
    df["log_y"] = np.log1p(pd.to_numeric(df["questions"], errors="coerce").fillna(0))
    bins = sorted(df["event_bin"].dropna().astype(int).unique())
    omit = -1

    def name(b: int) -> str:
        return f"aisub_bn{abs(b)}" if b < 0 else f"aisub_bp{b}"

    for b in bins:
        if b != omit:
            df[name(b)] = df["ai_sub"] * (df["event_bin"] == b).astype(int)
    terms = [name(b) for b in bins if b != omit]
    fit = pf.feols(f"log_y ~ {' + '.join(terms)} | tag_qtype + week_id", data=df, vcov={"CRV1": "tag"})
    co, se, pv, ci = fit.coef(), fit.se(), fit.pvalue(), fit.confint()
    rows = []
    for b in bins:
        if b == omit:
            rows.append({"event_bin": b, "calendar_period": bin_period(df, b), "beta": 0.0, "se": 0.0, "ci_low": 0.0, "ci_high": 0.0, "p_value": np.nan, "n_obs": int((df["event_bin"] == b).sum())})
            continue
        nm = name(b)
        rows.append({
            "event_bin": b,
            "calendar_period": bin_period(df, b),
            "beta": float(co[nm]),
            "se": float(se[nm]),
            "ci_low": float(ci.loc[nm, "2.5%"]),
            "ci_high": float(ci.loc[nm, "97.5%"]),
            "p_value": float(pv[nm]),
            "n_obs": int((df["event_bin"] == b).sum()),
        })
    out = pd.DataFrame(rows)
    args.table.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.table, index=False)

    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    ax.axhline(0, color="0.35", linestyle="--", linewidth=0.8)
    ax.axvline(-0.5, color="0.55", linewidth=0.8)
    x = out["event_bin"]
    ax.errorbar(x, out["beta"], yerr=1.96 * out["se"], fmt="o-", color="#334e68", ecolor="#8aa2b5", capsize=2)
    ax.set_xlabel("Quarterly event bin relative to ChatGPT release")
    ax.set_ylabel("AI answerability x substitutable coefficient")
    ax.set_title("Quarterly DDD Event Study Through Q4 2025")
    ax.set_xticks(x[::2])
    fig.tight_layout()
    args.figure.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.figure)
    plt.close(fig)
    print(f"saved {args.table}")
    print(f"saved {args.figure}")


if __name__ == "__main__":
    main()
