"""Re-estimate baseline DDD on 2020-2024 vs 2020-2025 full 100-tag panels."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf

THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.paths import PROCESSED_DIR, TABLES_DIR  # noqa: E402


def fit_ddd(df: pd.DataFrame, treatment: str) -> dict:
    d = df.copy()
    d["week_start"] = pd.to_datetime(d["week_start"])
    d["week_id"] = d["week_start"].dt.strftime("%Y-%m-%d")
    d["tag_qtype"] = d["tag"].astype(str) + "::" + d["question_type"].astype(str)
    d["ai"] = pd.to_numeric(d[treatment], errors="coerce")
    d["sub"] = pd.to_numeric(d["substitutable_type"], errors="coerce").astype(int)
    d["post"] = (d["week_start"] >= pd.Timestamp("2022-11-30")).astype(int)
    d["ai_post"] = d["ai"] * d["post"]
    d["ai_sub"] = d["ai"] * d["sub"]
    d["post_sub"] = d["post"] * d["sub"]
    d["ai_post_sub"] = d["ai"] * d["post"] * d["sub"]
    d["log_y"] = np.log1p(pd.to_numeric(d["questions"], errors="coerce").fillna(0))
    d = d.dropna(subset=["ai", "log_y", "tag", "week_id", "tag_qtype"])
    fit = pf.feols(
        "log_y ~ ai_post + ai_sub + post_sub + ai_post_sub | tag_qtype + week_id",
        data=d,
        vcov={"CRV1": "tag"},
    )
    return {
        "beta_ddd": float(fit.coef()["ai_post_sub"]),
        "se": float(fit.se()["ai_post_sub"]),
        "p_value": float(fit.pvalue()["ai_post_sub"]),
        "n_obs": int(fit._N),
        "n_tags": int(d["tag"].nunique()),
        "start_date": d["week_start"].min().strftime("%Y-%m-%d"),
        "end_date": d["week_start"].max().strftime("%Y-%m-%d"),
    }


def treatment_measures(df: pd.DataFrame) -> list[str]:
    out = ["ai_answerability_structural"]
    if "embedding_answerability" in df.columns:
        out.append("embedding_answerability")
    elif "ai_answerability_zscore" in df.columns:
        out.append("ai_answerability_zscore")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=PROCESSED_DIR / "panel_tag_week_question_type_2020_2025.csv")
    parser.add_argument("--output", type=Path, default=TABLES_DIR / "ddd_2020_2024_vs_2020_2025_full.csv")
    args = parser.parse_args()
    df = pd.read_csv(args.panel)
    df["week_start"] = pd.to_datetime(df["week_start"])
    rows = []
    for sample_name, sub in [
        ("2020-2024 full 100-tag sample", df[df["week_start"].dt.year <= 2024]),
        ("2020-2025 full 100-tag sample", df[df["week_start"].dt.year <= 2025]),
    ]:
        for treatment in treatment_measures(df):
            res = fit_ddd(sub, treatment)
            rows.append({
                "sample": sample_name,
                "treatment_measure": treatment,
                **res,
                "fixed_effects": "tag_question_type;week",
                "cluster_level": "tag",
            })
            print(sample_name, treatment, res)
    out = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
