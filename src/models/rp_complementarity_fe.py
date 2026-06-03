"""Complementarity test with tag fixed effects.

For each complexity outcome (body length, accepted-answer
share, code share), estimate:

    Y_{t,w} = alpha_t + beta * Post_w
            + gamma * Post_w * AI_t + epsilon

i.e., a tag-level panel of weekly mean complexity, with tag
fixed effects (alpha_t) absorbing all time-invariant tag
differences. The coefficient beta captures the aggregate
pre-post complexity shift; gamma captures whether the shift
is larger in higher-AI-answerability tags. A positive beta
in body_length / negative beta in accepted_share is evidence
of complementarity (harder questions remain). A positive
gamma in body_length / negative gamma in accepted_share is
evidence that complementarity is stronger in AI-answerable
tags.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")


def run(panel_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(panel_path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["post"] = (df["week_start"] >= CHATGPT_RELEASE).astype(int)
    df["ai"] = df["ai_answerability_structural"]

    # Tag-week aggregation
    weekly = df.groupby(["tag", "week_start"]).agg(
        body_length=("body_length_mean", "mean"),
        accepted_share=("accepted_share", "mean"),
        code_share=("code_share", "mean"),
        n_questions=("questions", "sum"),
        ai=("ai", "first"),
    ).reset_index()
    weekly["post"] = (weekly["week_start"] >= CHATGPT_RELEASE).astype(int)
    weekly["post_ai"] = weekly["post"] * weekly["ai"]
    weekly["week_id"] = weekly["week_start"].astype(str)

    rows = []
    for outcome in ["body_length", "accepted_share", "code_share"]:
        # Model A: Tag FE only, plus Post
        fit_a = pf.feols(
            f"{outcome} ~ post | tag",
            data=weekly,
            vcov={"CRV1": "tag"},
        )
        rows.append({
            "outcome": outcome,
            "spec": "tag_fe_post",
            "coef": float(fit_a.coef()["post"]),
            "se": float(fit_a.se()["post"]),
            "p": float(fit_a.pvalue()["post"]),
            "n": int(fit_a._N),
        })
        # Model B: Tag FE, Post, Post*AI
        fit_b = pf.feols(
            f"{outcome} ~ post + post_ai | tag",
            data=weekly,
            vcov={"CRV1": "tag"},
        )
        for v in ["post", "post_ai"]:
            rows.append({
                "outcome": outcome,
                "spec": f"tag_fe_post_postAI_{v}",
                "coef": float(fit_b.coef()[v]),
                "se": float(fit_b.se()[v]),
                "p": float(fit_b.pvalue()[v]),
                "n": int(fit_b._N),
            })

    out = pd.DataFrame(rows)
    csv = out_dir / "rp_complementarity_tag_fe.csv"
    out.to_csv(csv, index=False)
    print(f"saved {csv}\n")
    print(out.to_string(index=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", type=Path,
                   default=Path("data/processed/stackoverflow_question_type_master_panel.csv"))
    p.add_argument("--out-dir", type=Path, default=Path("outputs/tables"))
    args = p.parse_args()
    run(args.panel, args.out_dir)
