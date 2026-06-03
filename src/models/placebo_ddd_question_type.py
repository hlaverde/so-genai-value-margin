"""Placebos para la triple-diferencia question_type.

Dos pruebas:

(a) **Placebo de fecha**: restringimos la muestra a periodos puramente pre
    ChatGPT (`week_start < 2022-11-30`) y suponemos cutoffs falsos en
    2020-11-30, 2021-05-30, 2021-11-30 y 2022-05-30. Bajo H0 (no efecto
    real antes de ChatGPT), todos los DDD placebo deberían no ser
    significativos. Si encontramos efectos grandes, indica
    pre-trend confundente.

(b) **DDD con control de trend lineal**: agregamos un término
    (AI · Sub · t) que captura cualquier tendencia lineal sustituible-
    answerable común al periodo entero. El coeficiente DDD restante
    expresa el "salto" residual atribuible a ChatGPT.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")


def fit_ddd(df: pd.DataFrame, post_var: str, ai_col: str) -> dict:
    df = df.copy()
    df["sub"] = df["substitutable_type"].astype(int)
    df["ai"] = df[ai_col]
    df["ai_post"] = df["ai"] * df[post_var]
    df["ai_sub"] = df["ai"] * df["sub"]
    df["post_sub"] = df[post_var] * df["sub"]
    df["ai_post_sub"] = df["ai"] * df[post_var] * df["sub"]
    df["week_id"] = df["week_start"].astype(str)
    formula = (
        "log_questions_p1 ~ ai_post + ai_sub + post_sub + ai_post_sub "
        "| tag_qtype + week_id"
    )
    fit = pf.feols(formula, data=df, vcov={"CRV1": "tag"})
    coef = fit.coef()
    se = fit.se()
    pval = fit.pvalue()
    name = "ai_post_sub"
    return {
        "ddd": float(coef[name]),
        "se": float(se[name]),
        "p": float(pval[name]),
        "n": int(fit._N),
    }


def placebo_dates(panel_path: Path, out_dir: Path, ai_col: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(panel_path)
    df["week_start"] = pd.to_datetime(df["week_start"])

    # Sample restringido a estrictamente pre-ChatGPT
    pre = df[df["week_start"] < CHATGPT_RELEASE].reset_index(drop=True)
    print(f"Pre-ChatGPT sample: {len(pre)} rows")

    placebo_cuts = [
        pd.Timestamp("2020-05-30"),
        pd.Timestamp("2020-11-30"),
        pd.Timestamp("2021-05-30"),
        pd.Timestamp("2021-11-30"),
        pd.Timestamp("2022-05-30"),
    ]
    rows = []
    for cut in placebo_cuts:
        var = f"post_placebo"
        sub = pre.copy()
        sub[var] = (sub["week_start"] >= cut).astype(int)
        if sub[var].mean() in (0.0, 1.0):
            print(f"  {cut:%Y-%m-%d}: skip (no variation)")
            continue
        res = fit_ddd(sub, var, ai_col)
        rows.append({"placebo_cutoff": cut.strftime("%Y-%m-%d"), **res})
        print(
            f"  placebo {cut:%Y-%m-%d}: DDD = {res['ddd']:+.4f} "
            f"(SE {res['se']:.4f}, p={res['p']:.3g}, n={res['n']})"
        )

    # Real cutoff sobre muestra completa para comparar
    full = df.copy()
    full["post_real"] = (full["week_start"] >= CHATGPT_RELEASE).astype(int)
    real = fit_ddd(full, "post_real", ai_col)
    rows.append(
        {
            "placebo_cutoff": "REAL (2022-11-30)",
            **real,
        }
    )
    print(f"  REAL 2022-11-30: DDD = {real['ddd']:+.4f} (SE {real['se']:.4f}, p={real['p']:.3g}, n={real['n']})")

    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "placebo_dates_ddd_question_type.csv", index=False)
    print(f"\nsaved {out_dir / 'placebo_dates_ddd_question_type.csv'}")


def trend_adjusted_ddd(panel_path: Path, out_dir: Path, ai_col: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(panel_path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["sub"] = df["substitutable_type"].astype(int)
    df["ai"] = df[ai_col]
    df["post"] = (df["week_start"] >= CHATGPT_RELEASE).astype(int)

    # Tiempo numérico (semanas desde inicio)
    min_week = df["week_start"].min()
    df["t"] = ((df["week_start"] - min_week).dt.days // 7).astype(int)
    # Cuadrático opcional
    df["t2"] = df["t"] ** 2

    df["ai_post"] = df["ai"] * df["post"]
    df["ai_sub"] = df["ai"] * df["sub"]
    df["post_sub"] = df["post"] * df["sub"]
    df["ai_post_sub"] = df["ai"] * df["post"] * df["sub"]
    df["ai_sub_t"] = df["ai"] * df["sub"] * df["t"]
    df["ai_sub_t2"] = df["ai"] * df["sub"] * df["t2"]
    df["week_id"] = df["week_start"].astype(str)

    specs = [
        ("baseline", "ai_post + ai_sub + post_sub + ai_post_sub"),
        (
            "trend_linear",
            "ai_post + ai_sub + post_sub + ai_post_sub + ai_sub_t",
        ),
        (
            "trend_quadratic",
            "ai_post + ai_sub + post_sub + ai_post_sub + ai_sub_t + ai_sub_t2",
        ),
    ]
    rows = []
    for name, rhs in specs:
        formula = f"log_questions_p1 ~ {rhs} | tag_qtype + week_id"
        fit = pf.feols(formula, data=df, vcov={"CRV1": "tag"})
        coef = fit.coef()
        se = fit.se()
        p = fit.pvalue()
        rec = {
            "spec": name,
            "ddd": float(coef["ai_post_sub"]),
            "ddd_se": float(se["ai_post_sub"]),
            "ddd_p": float(p["ai_post_sub"]),
            "ai_sub_t": float(coef.get("ai_sub_t", np.nan)) if "ai_sub_t" in coef.index else np.nan,
            "ai_sub_t_p": float(p.get("ai_sub_t", np.nan)) if "ai_sub_t" in p.index else np.nan,
            "n": int(fit._N),
        }
        rows.append(rec)
        print(
            f"  {name}: DDD = {rec['ddd']:+.4f} (SE {rec['ddd_se']:.4f}, "
            f"p={rec['ddd_p']:.3g}); ai_sub_t = {rec['ai_sub_t']}"
        )
    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "trend_adjusted_ddd_question_type.csv", index=False)
    print(f"\nsaved {out_dir / 'trend_adjusted_ddd_question_type.csv'}")


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
    print("=== Placebo dates (pre-only sample with fake cutoffs) ===")
    placebo_dates(args.panel, args.out_dir, args.answerability)
    print("\n=== Trend-adjusted DDD (full sample) ===")
    trend_adjusted_ddd(args.panel, args.out_dir, args.answerability)


if __name__ == "__main__":
    main()
