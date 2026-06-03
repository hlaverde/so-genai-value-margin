"""Consolida en una sola tabla el DDD principal y todas sus robusteces.

Salida:
    outputs/tables/ddd_stress_test_table.csv
    outputs/tables/ddd_stress_test_table.tex

Estructura:
    Spec | beta | SE | p | n | comment
    --------------------------------------
    Baseline OLS log1p (z-score)         ...
    Alt answerability (PCA / Quantile / Structural)
    Outcome users
    Sample top-50
    PPML (Poisson FE)
    Trend-adjusted (linear / quadratic)
    Placebo cutoffs (5 dates)
    Wild bootstrap (Rademacher, 199 reps)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def safe_read(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--in-dir", type=Path, default=Path("outputs/tables"))
    p.add_argument("--out-csv", type=Path, default=Path("outputs/tables/ddd_stress_test_table.csv"))
    p.add_argument("--out-tex", type=Path, default=Path("outputs/tables/ddd_stress_test_table.tex"))
    args = p.parse_args()

    in_dir = args.in_dir
    main_df = safe_read(in_dir / "ddd_question_type_main.csv")
    placebo_df = safe_read(in_dir / "placebo_dates_ddd_question_type.csv")
    trend_df = safe_read(in_dir / "trend_adjusted_ddd_question_type.csv")
    boot_df = safe_read(in_dir / "wild_bootstrap_ddd_question_type.csv")
    twoway_df = safe_read(in_dir / "twoway_cluster_ddd_question_type.csv")
    matching_df = safe_read(in_dir / "matching_pretrend_ddd.csv")
    fractional_df = safe_read(in_dir / "fractional_ddd_question_type.csv")

    rows = []

    if main_df is not None:
        main_ddd = main_df[main_df["coef_name"] == "ai_post_sub"].copy()
        labels = {
            "main_ols_log1p_zscore_full": "Baseline OLS log(1+Q), z-score, full panel",
            "alt_ols_log1p_pca_full": "Answerability PCA",
            "alt_ols_log1p_quantile_full": "Answerability Quantile",
            "alt_ols_log1p_structural_full": "Answerability Structural",
            "sub_ols_log1p_zscore_top50": "Sub-sample top-50 tags",
            "alt_ols_log1p_zscore_users": "Outcome log(1+unique users)",
            "ppml_zscore_full": "PPML (Poisson FE)",
        }
        for _, r in main_ddd.iterrows():
            spec = r["spec"]
            label = labels.get(spec, spec)
            rows.append(
                {
                    "block": "Main + robustness",
                    "spec": label,
                    "estimate": r["estimate"],
                    "se": r["std_err"],
                    "p": r["p"],
                    "n": r["nobs"],
                    "comment": "",
                }
            )

    if trend_df is not None:
        for _, r in trend_df.iterrows():
            label_map = {
                "baseline": "Trend control: none (baseline replicated)",
                "trend_linear": "Trend control: linear (AI×Sub×t)",
                "trend_quadratic": "Trend control: quadratic (AI×Sub×t + ×t²)",
            }
            rows.append(
                {
                    "block": "Trend adjustment",
                    "spec": label_map.get(r["spec"], r["spec"]),
                    "estimate": r["ddd"],
                    "se": r["ddd_se"],
                    "p": r["ddd_p"],
                    "n": r["n"],
                    "comment": (
                        f"ai_sub_t={r['ai_sub_t']:.5g}" if pd.notna(r.get("ai_sub_t")) else ""
                    ),
                }
            )

    if placebo_df is not None:
        for _, r in placebo_df.iterrows():
            cutoff = r["placebo_cutoff"]
            tag = "Real cutoff" if "REAL" in cutoff else f"Placebo cutoff {cutoff}"
            rows.append(
                {
                    "block": "Placebo cutoffs",
                    "spec": tag,
                    "estimate": r["ddd"],
                    "se": r["se"],
                    "p": r["p"],
                    "n": r["n"],
                    "comment": (
                        "Pre-only sample, fake post" if "REAL" not in cutoff
                        else "Full sample, true post"
                    ),
                }
            )

    if twoway_df is not None:
        # Solo la fila de two-way clustering (las otras dos replican CR1)
        tw = twoway_df[twoway_df["cluster"].str.startswith("twoway")]
        for _, r in tw.iterrows():
            rows.append(
                {
                    "block": "Inference",
                    "spec": "Two-way clustering (tag + week)",
                    "estimate": r["estimate"],
                    "se": r["se"],
                    "p": r["p"],
                    "n": "—",
                    "comment": "linearmodels.PanelOLS",
                }
            )

    if fractional_df is not None:
        # Solo la fila fractional (la integer ya está en main)
        frac = fractional_df[fractional_df["outcome"] == "log_q_frac_p1"]
        for _, r in frac.iterrows():
            rows.append(
                {
                    "block": "Inference",
                    "spec": "Fractional tag counts (Q/n_top_tags)",
                    "estimate": r["ddd"],
                    "se": r["se"],
                    "p": r["p"],
                    "n": r["n"],
                    "comment": "Weighted by 1/n_top_tags per question",
                }
            )

    if matching_df is not None:
        for _, r in matching_df.iterrows():
            label_map = {
                "baseline_full": None,  # se omite, ya en main
                "slope_q1": "Stratum: slope quartile 1 (steepest decline)",
                "slope_q2": "Stratum: slope quartile 2",
                "slope_q3": "Stratum: slope quartile 3",
                "slope_q4": "Stratum: slope quartile 4 (steepest growth)",
                "cem_matched_pairs": "CEM matched pairs (all eligible)",
                "interquartile_band": "Interquartile band on pre-slope",
            }
            label = label_map.get(r["spec"])
            if label is None:
                continue
            rows.append(
                {
                    "block": "Pre-trend matching",
                    "spec": label,
                    "estimate": r["ddd"],
                    "se": r["se"],
                    "p": r["p"],
                    "n": r["n"],
                    "comment": f"n_tags={r['n_tags']}",
                }
            )

    if boot_df is not None:
        for _, r in boot_df.iterrows():
            rows.append(
                {
                    "block": "Inference",
                    "spec": "Wild cluster bootstrap (Rademacher, 199 reps, cluster=tag)",
                    "estimate": r["estimate"],
                    "se": r["se_crv1"],
                    "p": r["p_wild_boot"],
                    "n": "—",
                    "comment": f"CRV1 p={r['p_crv1']:.4f}",
                }
            )

    out = pd.DataFrame(rows)
    out["estimate"] = out["estimate"].astype(float)
    out["se"] = out["se"].astype(float)
    out["p"] = out["p"].astype(float)

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out_csv, index=False)
    print(f"saved {args.out_csv}")

    # LaTeX
    def fmt(x, n=4):
        if pd.isna(x):
            return "—"
        return f"{x:.{n}f}"

    def stars(p):
        if pd.isna(p):
            return ""
        if p < 0.01:
            return "$^{***}$"
        if p < 0.05:
            return "$^{**}$"
        if p < 0.10:
            return "$^{*}$"
        return ""

    lines = []
    lines.append(r"\begin{table}[h]")
    lines.append(r"\centering")
    lines.append(r"\small")
    lines.append(r"\caption{Triple-difference $\hat\beta_{\text{DDD}}$ across specifications and robustness checks.}")
    lines.append(r"\label{tab:ddd_stress_test}")
    lines.append(r"\begin{tabular}{lrrrr}")
    lines.append(r"\toprule")
    lines.append(r"Specification & $\hat\beta_{\text{DDD}}$ & SE & $p$ & N \\")
    lines.append(r"\midrule")

    current_block = None
    for _, r in out.iterrows():
        if r["block"] != current_block:
            if current_block is not None:
                lines.append(r"\midrule")
            lines.append(r"\multicolumn{5}{l}{\textit{" + r["block"] + r"}} \\")
            current_block = r["block"]
        n_str = str(r["n"]) if r["n"] != "—" else r["n"]
        spec_tex = r["spec"]
        # Escape underscore OUTSIDE math first (we don't have math in spec)
        spec_tex = spec_tex.replace("_", r"\_")
        # Then map UTF-8 math chars to LaTeX
        spec_tex = spec_tex.replace("×", r"$\times$")
        spec_tex = spec_tex.replace("²", r"$^2$")
        lines.append(
            f"  {spec_tex} "
            f"& {fmt(r['estimate'])}{stars(r['p'])} "
            f"& {fmt(r['se'])} "
            f"& {fmt(r['p'], 3)} "
            f"& {n_str} \\\\"
        )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\begin{minipage}{0.9\textwidth}")
    lines.append(r"\footnotesize")
    lines.append(
        r"Notes. Baseline regression: $\log(1+Q_{t,w,k}) = \beta_{\text{DDD}} (\text{AI}_t \times \text{Post}_w \times \text{Sub}_k) + \gamma_1 (\text{AI}_t \times \text{Post}_w) + \gamma_2 (\text{AI}_t \times \text{Sub}_k) + \gamma_3 (\text{Post}_w \times \text{Sub}_k) + \alpha_{t,k} + \delta_w + \varepsilon$, with FE tag$\times$question-type and week, errors clustered by tag (CR1). $^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$."
    )
    lines.append(r"\end{minipage}")
    lines.append(r"\end{table}")

    args.out_tex.parent.mkdir(parents=True, exist_ok=True)
    args.out_tex.write_text("\n".join(lines), encoding="utf-8")
    print(f"saved {args.out_tex}")

    # Print summary to stdout
    print("\n=== STRESS TEST TABLE ===")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
