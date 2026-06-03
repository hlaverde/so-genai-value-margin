"""DDD restringido a sub-muestras balanceadas en tendencia pre-tratamiento.

Idea: el problema de pre-trends en el panel agregado puede deberse a que
tags con alta AI-answerability tenían (de por sí) tendencias seculares
distintas que tags con baja answerability. Si "matchamos" pares de
tags con tendencias pre similares pero scores de answerability distintos
y reestimamos el DDD, el sesgo por tendencias divergentes debe
desaparecer.

Procedimiento:
    1. Para cada tag, calcular la pendiente lineal de log(1+Q) sobre el
       periodo pre-tratamiento (2020-01-01 a 2022-11-30), agregando
       todas las question_types.
    2. Discretizar la pendiente en quartiles (Q1=más decreciente,
       Q4=más creciente).
    3. Dentro de cada quartil, re-estimar el DDD principal. Si el
       efecto persiste en cada strata, no es trend-driven.
    4. Alternativa robusta: coarsened exact matching (CEM) entre
       tags high-AI y low-AI, exigiendo igualdad de quartil de slope.
       Re-estimar DDD sobre la unión de pares matched.

Salida:
    outputs/tables/matching_pretrend_ddd.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")
PRE_START = pd.Timestamp("2020-01-01")


def compute_tag_slopes(panel: pd.DataFrame) -> pd.DataFrame:
    """Slope lineal de log(1+Q_tag) por semana en periodo pretratamiento."""
    pre = panel[
        (panel["week_start"] >= PRE_START)
        & (panel["week_start"] < CHATGPT_RELEASE)
    ].copy()
    # Agregar question_types -> total semanal por tag
    weekly = (
        pre.groupby(["tag", "week_start"])["questions"].sum().reset_index()
    )
    weekly["log_q"] = np.log1p(weekly["questions"])
    weekly["t"] = (
        (weekly["week_start"] - PRE_START).dt.days // 7
    ).astype(int)

    slopes = []
    for tag, sub in weekly.groupby("tag"):
        if len(sub) < 10:
            continue
        x = sub["t"].values
        y = sub["log_q"].values
        # OLS simple
        slope, intercept = np.polyfit(x, y, 1)
        slopes.append({"tag": tag, "pre_slope": slope, "n_pre_weeks": len(sub)})
    return pd.DataFrame(slopes)


def assign_quartiles(slopes_df: pd.DataFrame, n_q: int = 4) -> pd.DataFrame:
    slopes_df = slopes_df.copy()
    slopes_df["slope_q"] = pd.qcut(
        slopes_df["pre_slope"], n_q, labels=list(range(1, n_q + 1))
    ).astype(int)
    return slopes_df


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


def coarsened_match(
    panel: pd.DataFrame,
    slopes_df: pd.DataFrame,
    ai_col: str,
    n_q_slope: int = 4,
    n_q_ai: int = 2,
) -> pd.DataFrame:
    """CEM: tag high-AI ↔ tag low-AI con misma slope_q. Conserva tags
    sólo si su slope_q contiene al menos 1 high-AI y 1 low-AI.
    """
    ai_lookup = (
        panel.groupby("tag")[ai_col].first().rename("ai").reset_index()
    )
    merged = slopes_df.merge(ai_lookup, on="tag", how="inner")
    merged["ai_q"] = pd.qcut(
        merged["ai"], n_q_ai, labels=["low", "high"]
    )
    coverage = (
        merged.groupby("slope_q")["ai_q"].nunique().rename("n_ai_groups")
    )
    eligible_slopes = coverage[coverage >= 2].index.tolist()
    matched = merged[merged["slope_q"].isin(eligible_slopes)]
    return matched


def run(panel_path: Path, out_dir: Path, ai_col: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(panel_path)
    panel["week_start"] = pd.to_datetime(panel["week_start"])

    print("[1] Calculando pre-slopes por tag...")
    slopes = compute_tag_slopes(panel)
    slopes = assign_quartiles(slopes)
    slopes_csv = out_dir / "matching_pretrend_slopes.csv"
    slopes.to_csv(slopes_csv, index=False)
    print(f"     guardado {slopes_csv} ({len(slopes)} tags)")

    rows = []

    # (a) Baseline full
    base = fit_ddd(panel, ai_col)
    rows.append({"spec": "baseline_full", **base})
    print(f"     baseline: DDD = {base['ddd']:+.4f} (SE {base['se']:.4f}, p={base['p']:.3g})")

    # (b) Estratificado por quartil de pre-slope
    print("\n[2] DDD estratificado por quartil de slope pretratamiento")
    panel = panel.merge(slopes[["tag", "pre_slope", "slope_q"]], on="tag", how="left")
    for q in sorted(panel["slope_q"].dropna().unique()):
        sub = panel[panel["slope_q"] == q]
        try:
            r = fit_ddd(sub, ai_col)
        except Exception as exc:
            print(f"  slope_q={q}: failed ({exc})")
            continue
        rows.append({"spec": f"slope_q{int(q)}", **r})
        print(
            f"  slope_q={int(q)}: n_tags={r['n_tags']:>3}  "
            f"DDD = {r['ddd']:+.4f} (SE {r['se']:.4f}, p={r['p']:.3g})"
        )

    # (c) CEM (matched sample)
    print("\n[3] CEM: tags con high-AI y low-AI dentro del mismo quartil de slope")
    matched = coarsened_match(panel, slopes, ai_col)
    matched_tags = matched["tag"].unique()
    sub = panel[panel["tag"].isin(matched_tags)]
    if len(sub) > 0:
        r = fit_ddd(sub, ai_col)
        rows.append({"spec": "cem_matched_pairs", **r})
        print(
            f"  CEM: n_tags={r['n_tags']:>3}  "
            f"DDD = {r['ddd']:+.4f} (SE {r['se']:.4f}, p={r['p']:.3g})"
        )

    # (d) Solo tags con slope cercana a la mediana (banda intercuartílica)
    median_slope = slopes["pre_slope"].median()
    iqr = slopes["pre_slope"].quantile(0.75) - slopes["pre_slope"].quantile(0.25)
    band = (slopes["pre_slope"] - median_slope).abs() <= iqr
    band_tags = slopes.loc[band, "tag"].tolist()
    sub = panel[panel["tag"].isin(band_tags)]
    r = fit_ddd(sub, ai_col)
    rows.append({"spec": "interquartile_band", **r})
    print(
        f"  interquartile band: n_tags={r['n_tags']:>3}  "
        f"DDD = {r['ddd']:+.4f} (SE {r['se']:.4f}, p={r['p']:.3g})"
    )

    out = pd.DataFrame(rows)
    out_csv = out_dir / "matching_pretrend_ddd.csv"
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
