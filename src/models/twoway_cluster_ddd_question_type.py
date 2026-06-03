"""DDD principal re-estimado con clustering en dos dimensiones (tag, week).

Cameron-Gelbach-Miller (2011) muestran que cuando los errores están
correlacionados tanto cross-sectionally (entre tags) como serialmente
(entre semanas), se necesita clustering en ambas dimensiones para
inferencia válida. Implementado con pyfixest `vcov="twoway"` style
(`{"CRV1": [tag, week_id]}`).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")


def run(panel_path: Path, out_dir: Path, ai_col: str) -> None:
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

    formula = (
        "log_questions_p1 ~ ai_post + ai_sub + post_sub + ai_post_sub "
        "| tag_qtype + week_id"
    )

    print("[1] CR1 cluster por tag")
    fit_tag = pf.feols(formula, data=df, vcov={"CRV1": "tag"})
    se_tag = float(fit_tag.se()["ai_post_sub"])
    p_tag = float(fit_tag.pvalue()["ai_post_sub"])
    beta = float(fit_tag.coef()["ai_post_sub"])
    print(f"  beta = {beta:+.4f}, SE_tag = {se_tag:.4f}, p = {p_tag:.4f}")

    print("[2] CR1 cluster por week_id")
    fit_week = pf.feols(formula, data=df, vcov={"CRV1": "week_id"})
    se_week = float(fit_week.se()["ai_post_sub"])
    p_week = float(fit_week.pvalue()["ai_post_sub"])
    print(f"  SE_week = {se_week:.4f}, p = {p_week:.4f}")

    print("[3] Two-way clustering por tag + week_id (linearmodels.PanelOLS)")
    from linearmodels.panel import PanelOLS

    pdf = df.copy()
    # PanelOLS exige MultiIndex (entity, time).
    pdf = pdf.set_index(["tag_qtype", "week_start"])
    # ai_sub está absorbido por EntityEffects (tag_qtype). Quitamos a mano.
    mod = PanelOLS.from_formula(
        "log_questions_p1 ~ ai_post + post_sub + ai_post_sub "
        "+ EntityEffects + TimeEffects",
        data=pdf,
    )
    # Cluster por TAG (no tag_qtype) y por week
    clusters = pdf.reset_index()[["tag", "week_start"]]
    clusters.index = pdf.index
    res_tw = mod.fit(
        cov_type="clustered",
        clusters=clusters[["tag", "week_start"]],
    )
    beta_tw = float(res_tw.params["ai_post_sub"])
    se_tw = float(res_tw.std_errors["ai_post_sub"])
    p_tw = float(res_tw.pvalues["ai_post_sub"])
    print(f"  beta_tw = {beta_tw:+.4f}, SE_twoway = {se_tw:.4f}, p = {p_tw:.4f}")

    out = pd.DataFrame(
        [
            {"cluster": "tag", "se": se_tag, "p": p_tag, "estimate": beta},
            {"cluster": "week_id", "se": se_week, "p": p_week, "estimate": beta},
            {"cluster": "twoway (tag + week_id)", "se": se_tw, "p": p_tw, "estimate": beta},
        ]
    )
    out_csv = out_dir / "twoway_cluster_ddd_question_type.csv"
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
    args = p.parse_args()
    run(args.panel, args.out_dir, args.answerability)


if __name__ == "__main__":
    main()
