"""Wild cluster bootstrap (Cameron-Gelbach-Miller 2008) sobre la triple
diferencia, clusters por tag (n=100). Implementa Rademacher por defecto;
reps=999 para inferencia razonable. Reporta p-value comparable al CRV1.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")


def run(
    panel_path: Path,
    out_dir: Path,
    ai_col: str = "ai_answerability_zscore",
    reps: int = 999,
    seed: int = 20251122,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(panel_path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["sub"] = df["substitutable_type"].astype(int)
    df["ai"] = df[ai_col]
    df["post"] = (df["week_start"] >= CHATGPT_RELEASE).astype(int)
    df["ai_post"] = df["ai"] * df["post"]
    df["ai_sub"] = df["ai"] * df["sub"]
    df["post_sub"] = df["post"] * df["sub"]
    df["ai_post_sub"] = df["ai"] * df["post"] * df["sub"]
    df["week_id"] = df["week_start"].astype(str)
    # wildboottest exige cluster numérico (no string)
    df["tag_int"] = pd.Categorical(df["tag"]).codes.astype(np.int64)

    formula = (
        "log_questions_p1 ~ ai_post + ai_sub + post_sub + ai_post_sub "
        "| tag_qtype + week_id"
    )
    fit = pf.feols(formula, data=df, vcov={"CRV1": "tag_int"})
    coef = float(fit.coef()["ai_post_sub"])
    se_crv1 = float(fit.se()["ai_post_sub"])
    p_crv1 = float(fit.pvalue()["ai_post_sub"])
    print(f"Baseline CRV1:  beta = {coef:+.4f}, SE = {se_crv1:.4f}, p = {p_crv1:.4f}")

    # Wild cluster bootstrap, Rademacher, impose null = True
    print(f"\nRunning wild cluster bootstrap (reps={reps}, seed={seed})...")
    boot = fit.wildboottest(
        reps=reps,
        cluster="tag_int",
        param="ai_post_sub",
        weights_type="rademacher",
        impose_null=True,
        bootstrap_type="11",
        seed=seed,
    )
    print("\nWild bootstrap result:")
    print(boot.to_string(index=False) if isinstance(boot, pd.DataFrame) else boot)

    # Persistir
    rows = []
    if isinstance(boot, pd.DataFrame):
        for _, r in boot.iterrows():
            rows.append(
                {
                    "param": r.get("param", "ai_post_sub"),
                    "estimate": coef,
                    "se_crv1": se_crv1,
                    "p_crv1": p_crv1,
                    "p_wild_boot": float(r["Pr(>|t|)"]) if "Pr(>|t|)" in r.index else float(r.get("Pr(>|t|)", np.nan)),
                    "stat": float(r.get("statistic", np.nan)),
                    "reps": reps,
                }
            )
    else:
        rows.append(
            {
                "param": "ai_post_sub",
                "estimate": coef,
                "se_crv1": se_crv1,
                "p_crv1": p_crv1,
                "p_wild_boot": float("nan"),
                "reps": reps,
                "raw": str(boot),
            }
        )
    out = pd.DataFrame(rows)
    out_csv = out_dir / "wild_bootstrap_ddd_question_type.csv"
    out.to_csv(out_csv, index=False)
    print(f"\nsaved {out_csv}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--panel",
        type=Path,
        default=Path("data/processed/stackoverflow_question_type_master_panel.csv"),
    )
    p.add_argument("--out-dir", type=Path, default=Path("outputs/tables"))
    p.add_argument("--answerability", default="ai_answerability_zscore")
    p.add_argument("--reps", type=int, default=999)
    p.add_argument("--seed", type=int, default=20251122)
    args = p.parse_args()
    run(args.panel, args.out_dir, args.answerability, args.reps, args.seed)


if __name__ == "__main__":
    main()
