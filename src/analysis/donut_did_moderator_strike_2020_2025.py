"""Baseline DDD with and without the June-August 2023 moderator-strike window."""

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

STRIKE_START = pd.Timestamp("2023-06-01")
STRIKE_END = pd.Timestamp("2023-09-01")


def fit(df: pd.DataFrame, treatment: str) -> dict:
    d = df.copy()
    d["week_start"] = pd.to_datetime(d["week_start"])
    d["week_id"] = d["week_start"].dt.strftime("%Y-%m-%d")
    d["tag_qtype"] = d["tag"].astype(str) + "::" + d["question_type"].astype(str)
    d["ai"] = pd.to_numeric(d[treatment], errors="coerce")
    d["sub"] = pd.to_numeric(d["substitutable_type"], errors="coerce").fillna(0).astype(int)
    d["post"] = (d["week_start"] >= pd.Timestamp("2022-11-30")).astype(int)
    d["ai_post"] = d["ai"] * d["post"]
    d["ai_sub"] = d["ai"] * d["sub"]
    d["post_sub"] = d["post"] * d["sub"]
    d["ai_post_sub"] = d["ai"] * d["post"] * d["sub"]
    d["log_y"] = np.log1p(pd.to_numeric(d["questions"], errors="coerce").fillna(0))
    m = pf.feols("log_y ~ ai_post + ai_sub + post_sub + ai_post_sub | tag_qtype + week_id", data=d, vcov={"CRV1": "tag"})
    return {"beta_ddd": float(m.coef()["ai_post_sub"]), "se": float(m.se()["ai_post_sub"]), "p_value": float(m.pvalue()["ai_post_sub"]), "n_obs": int(m._N), "n_tags": int(d["tag"].nunique())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=PROCESSED_DIR / "panel_tag_week_question_type_2020_2025.csv")
    parser.add_argument("--treatment", default="ai_answerability_structural")
    parser.add_argument("--output", type=Path, default=TABLES_DIR / "donut_did_moderator_strike_2020_2025.csv")
    args = parser.parse_args()
    df = pd.read_csv(args.panel)
    df["week_start"] = pd.to_datetime(df["week_start"])
    full = df[df["week_start"].dt.year <= 2025]
    donut = full[~((full["week_start"] >= STRIKE_START) & (full["week_start"] < STRIKE_END))]
    rows = []
    for label, sub, excluded in [
        ("full_2020_2025", full, "none"),
        ("donut_excluding_moderator_strike", donut, "2023-06-01 to 2023-08-31"),
    ]:
        rows.append({"sample": label, "excluded_window": excluded, **fit(sub, args.treatment)})
    out = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    print(out.to_string(index=False))
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
