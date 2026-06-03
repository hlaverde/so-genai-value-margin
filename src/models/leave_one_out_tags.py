"""Leave-one-out (LOO) y leave-N-out sobre tags grandes.

Re-estima el DDD principal excluyendo:
    - top-1 tag (python típicamente)
    - top-5 tags
    - top-10 tags
    - top-20 tags
    - Cada uno de los top-10 tags por separado (jackknife)

Demuestra que el efecto no depende de un puñado de tags grandes.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")


def fit_ddd(df: pd.DataFrame, ai_col: str) -> dict:
    df = df.copy()
    df["sub"] = df["substitutable_type"].astype(int)
    df["ai"] = df[ai_col]
    df["post"] = (df["week_start"] >= CHATGPT_RELEASE).astype(int)
    df["ai_post"] = df["ai"] * df["post"]
    df["ai_sub"] = df["ai"] * df["sub"]
    df["post_sub"] = df["post"] * df["sub"]
    df["ai_post_sub"] = df["ai"] * df["post"] * df["sub"]
    df["week_id"] = df["week_start"].astype(str)
    formula = (
        "log_questions_p1 ~ ai_post + ai_sub + post_sub + ai_post_sub "
        "| tag_qtype + week_id"
    )
    fit = pf.feols(formula, data=df, vcov={"CRV1": "tag"})
    return {
        "ddd": float(fit.coef()["ai_post_sub"]),
        "se": float(fit.se()["ai_post_sub"]),
        "p": float(fit.pvalue()["ai_post_sub"]),
        "n": int(fit._N),
        "n_tags": df["tag"].nunique(),
    }


def main(panel_path: Path, out_csv: Path, ai_col: str) -> None:
    df = pd.read_csv(panel_path)
    df["week_start"] = pd.to_datetime(df["week_start"])

    # Top tags by pre-treatment volume
    pre = df[df["week_start"] < CHATGPT_RELEASE]
    tag_volume = pre.groupby("tag")["questions"].sum().sort_values(ascending=False)
    top_20 = tag_volume.head(20).index.tolist()

    rows = []

    # Baseline
    r = fit_ddd(df, ai_col)
    rows.append({"spec": "baseline_all_100", **r, "excluded": ""})
    print(f"baseline_all_100  DDD = {r['ddd']:+.4f} (SE {r['se']:.4f}, p={r['p']:.3g}, n_tags={r['n_tags']})")

    # Leave top-N out
    for n in [1, 5, 10, 20]:
        excluded = top_20[:n]
        sub = df[~df["tag"].isin(excluded)]
        r = fit_ddd(sub, ai_col)
        rows.append(
            {
                "spec": f"drop_top_{n}",
                **r,
                "excluded": ",".join(excluded),
            }
        )
        print(
            f"drop_top_{n:>2d}        DDD = {r['ddd']:+.4f} "
            f"(SE {r['se']:.4f}, p={r['p']:.3g}, n_tags={r['n_tags']})  "
            f"excluded={','.join(excluded[:3])}..."
        )

    # Jackknife each top-10 tag
    print("\n=== Jackknife top-10 individuales ===")
    for tag in top_20[:10]:
        sub = df[df["tag"] != tag]
        r = fit_ddd(sub, ai_col)
        rows.append(
            {
                "spec": f"drop_{tag}",
                **r,
                "excluded": tag,
            }
        )
        print(
            f"  drop {tag:>20s}  DDD = {r['ddd']:+.4f} "
            f"(SE {r['se']:.4f}, p={r['p']:.3g}, n_tags={r['n_tags']})"
        )

    out = pd.DataFrame(rows)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)
    print(f"\nsaved {out_csv}")
    print(f"\nRange of DDD across all robustness specs: "
          f"[{out['ddd'].min():+.4f}, {out['ddd'].max():+.4f}]")
    print(f"Mean DDD: {out['ddd'].mean():+.4f}")
    print(f"All p < 0.05? {(out['p'] < 0.05).all()}")
    print(f"All negative? {(out['ddd'] < 0).all()}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--panel",
        type=Path,
        default=Path("data/processed/stackoverflow_question_type_master_panel.csv"),
    )
    p.add_argument(
        "--out-csv",
        type=Path,
        default=Path("outputs/tables/leave_one_out_tags.csv"),
    )
    p.add_argument("--answerability", default="ai_answerability_zscore")
    args = p.parse_args()
    main(args.panel, args.out_csv, args.answerability)
