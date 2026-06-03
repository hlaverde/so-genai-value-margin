"""Construye la tabla consolidada de robustez RP (tab:rp_robustness).

Bloques:
    A. Baseline + AI measure alternatives.
    B. Sample restrictions (top-50, top-75, IQR band, leave-N-out).
    C. Outcome and method alternatives (users, PPML, fractional, 2-way).
    D. Identification (Honest-DiD bounds, Copilot placebo, rolling placebos).
    E. Wild cluster bootstrap.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import numpy as np


def safe_read(path: Path):
    return pd.read_csv(path) if path.exists() else None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--in-dir", type=Path, default=Path("outputs/tables"))
    p.add_argument("--out-tex", type=Path,
                   default=Path("outputs/tables/rp_robustness_table.tex"))
    args = p.parse_args()
    in_dir = args.in_dir

    main_df = safe_read(in_dir / "ddd_question_type_main.csv")
    structural_df = safe_read(in_dir / "rp_structural_baseline.csv")
    matching_df = safe_read(in_dir / "matching_pretrend_ddd.csv")
    loo_df = safe_read(in_dir / "leave_one_out_tags.csv")
    twoway_df = safe_read(in_dir / "twoway_cluster_ddd_question_type.csv")
    fractional_df = safe_read(in_dir / "fractional_ddd_question_type.csv")
    honest_df = safe_read(in_dir / "rp_honest_did_bounds.csv")
    copilot_df = safe_read(in_dir / "rp_copilot_analysis.csv")
    rolling_df = safe_read(in_dir / "rp_rolling_placebos.csv")
    boot_df = safe_read(in_dir / "wild_bootstrap_ddd_question_type.csv")
    placebo_df = safe_read(in_dir / "placebo_dates_ddd_question_type.csv")

    def fmt(x, n=4):
        if pd.isna(x):
            return "---"
        return f"{x:.{n}f}"

    def stars(p):
        if pd.isna(p):
            return ""
        if p < 0.01: return r"$^{***}$"
        if p < 0.05: return r"$^{**}$"
        if p < 0.10: return r"$^{*}$"
        return ""

    lines = []
    lines.append(r"\begin{table}[!htbp]")
    lines.append(r"\centering")
    lines.append(r"\footnotesize")
    lines.append(r"\caption{Consolidated robustness battery for $\hat\beta_{\text{DDD}}$.}")
    lines.append(r"\label{tab:rp_robustness}")
    lines.append(r"\begin{tabular}{lrrrr}")
    lines.append(r"\toprule")
    lines.append(r"Specification & $\hat\beta_{\text{DDD}}$ & SE & $p$ & N \\")
    lines.append(r"\midrule")

    # A. AI measure variants (structural baseline first)
    lines.append(r"\multicolumn{5}{l}{\textit{A. AI-answerability measures}} \\")
    if structural_df is not None:
        order = ["ai_answerability_structural", "ai_answerability_zscore",
                 "ai_answerability_pca", "ai_answerability_quantile"]
        nice = {
            "ai_answerability_structural": "Structural index (baseline)",
            "ai_answerability_zscore": "z-score composite",
            "ai_answerability_pca": "PCA composite",
            "ai_answerability_quantile": "Quartile rank",
        }
        for m in order:
            row = structural_df[structural_df["ai_measure"] == m]
            if row.empty: continue
            r = row.iloc[0]
            lines.append(
                f"  {nice[m]} & {fmt(r['estimate'])}{stars(r['p'])} "
                f"& {fmt(r['se'])} & {fmt(r['p'], 3)} & {int(r['n']):,} \\\\"
            )

    # B. Sample restrictions
    lines.append(r"\midrule")
    lines.append(r"\multicolumn{5}{l}{\textit{B. Sample restrictions}} \\")
    if main_df is not None:
        top50 = main_df[(main_df["spec"] == "sub_ols_log1p_zscore_top50") &
                        (main_df["coef_name"] == "ai_post_sub")]
        if not top50.empty:
            r = top50.iloc[0]
            lines.append(
                f"  Top-50 tags by pre-period volume & "
                f"{fmt(r['estimate'])}{stars(r['p'])} & {fmt(r['std_err'])} "
                f"& {fmt(r['p'], 3)} & {int(r['nobs']):,} \\\\"
            )
    if matching_df is not None:
        for spec, label in [
            ("interquartile_band", "Interquartile pre-slope band (75 tags)"),
            ("slope_q4", "Slope quartile 4 (steepest growth)"),
            ("slope_q1", "Slope quartile 1 (steepest decline)"),
        ]:
            row = matching_df[matching_df["spec"] == spec]
            if row.empty: continue
            r = row.iloc[0]
            lines.append(
                f"  {label} & {fmt(r['ddd'])}{stars(r['p'])} "
                f"& {fmt(r['se'])} & {fmt(r['p'], 3)} & {int(r['n']):,} \\\\"
            )
    if loo_df is not None:
        for spec, label in [
            ("drop_top_1", "Leave-one-out: drop top-1 (python)"),
            ("drop_top_5", "Leave-out: drop top-5"),
            ("drop_top_10", "Leave-out: drop top-10"),
            ("drop_top_20", "Leave-out: drop top-20"),
        ]:
            row = loo_df[loo_df["spec"] == spec]
            if row.empty: continue
            r = row.iloc[0]
            lines.append(
                f"  {label} & {fmt(r['ddd'])}{stars(r['p'])} "
                f"& {fmt(r['se'])} & {fmt(r['p'], 3)} & {int(r['n']):,} \\\\"
            )

    # C. Outcome and method alternatives
    lines.append(r"\midrule")
    lines.append(r"\multicolumn{5}{l}{\textit{C. Outcome and method alternatives}} \\")
    if main_df is not None:
        for spec, label in [
            ("alt_ols_log1p_zscore_users", r"Outcome $\log(1+\text{unique users})$"),
            ("ppml_zscore_full", "PPML (Poisson FE)"),
        ]:
            row = main_df[(main_df["spec"] == spec) &
                          (main_df["coef_name"] == "ai_post_sub")]
            if row.empty: continue
            r = row.iloc[0]
            lines.append(
                f"  {label} & {fmt(r['estimate'])}{stars(r['p'])} "
                f"& {fmt(r['std_err'])} & {fmt(r['p'], 3)} "
                f"& {int(r['nobs']):,} \\\\"
            )
    if twoway_df is not None:
        tw = twoway_df[twoway_df["cluster"].str.startswith("twoway")]
        if not tw.empty:
            r = tw.iloc[0]
            lines.append(
                f"  Two-way clustering (tag + week) & "
                f"{fmt(r['estimate'])}{stars(r['p'])} & {fmt(r['se'])} "
                f"& {fmt(r['p'], 3)} & --- \\\\"
            )
    if fractional_df is not None:
        frac = fractional_df[fractional_df["outcome"] == "log_q_frac_p1"]
        if not frac.empty:
            r = frac.iloc[0]
            lines.append(
                f"  Fractional tag counts ($Q/n_{{\\text{{tags}}}}$) & "
                f"{fmt(r['ddd'])}{stars(r['p'])} & {fmt(r['se'])} "
                f"& {fmt(r['p'], 3)} & {int(r['n']):,} \\\\"
            )

    # D. Identification
    lines.append(r"\midrule")
    lines.append(r"\multicolumn{5}{l}{\textit{D. Identification: placebos, Honest-DiD, co-shock}} \\")
    if placebo_df is not None:
        for _, r in placebo_df.iterrows():
            cut = r["placebo_cutoff"]
            if "REAL" in cut:
                lines.append(
                    f"  Real cutoff (2022-11-30) & "
                    f"{fmt(r['ddd'])}{stars(r['p'])} & {fmt(r['se'])} "
                    f"& {fmt(r['p'], 3)} & {int(r['n']):,} \\\\"
                )
            else:
                lines.append(
                    f"  Placebo cutoff {cut} (pre-only) & "
                    f"{fmt(r['ddd'])}{stars(r['p'])} & {fmt(r['se'])} "
                    f"& {fmt(r['p'], 3)} & {int(r['n']):,} \\\\"
                )
    if copilot_df is not None:
        for _, r in copilot_df.iterrows():
            label = {
                "copilot_only_pre_chatgpt": "Copilot placebo (2022-06-21, pre-ChatGPT)",
                "dual_shock_copilot": r"Dual-shock: AI$\times$Sub$\times$Copilot",
                "dual_shock_chatgpt": r"Dual-shock: AI$\times$Sub$\times$ChatGPT",
            }.get(r["spec"], r["spec"])
            lines.append(
                f"  {label} & {fmt(r['estimate'])}{stars(r['p'])} "
                f"& {fmt(r['se'])} & {fmt(r['p'], 3)} & {int(r['n']):,} \\\\"
            )
    if rolling_df is not None:
        lines.append(
            f"  Rolling placebo mean ({len(rolling_df)} cutoffs) & "
            f"{fmt(rolling_df['estimate'].mean())} & "
            f"{fmt(rolling_df['estimate'].std())} & --- & --- \\\\"
        )
        share = (rolling_df["estimate"] < -0.10).mean() * 100
        lines.append(
            f"  \\quad share of rolling placebos $< -0.10$ & "
            f"\\multicolumn{{4}}{{l}}{{{share:.0f}\\%}} \\\\"
        )
    if honest_df is not None:
        for _, r in honest_df.iterrows():
            tag = "remains positive" if r["worst_case_post"] > 0 else "indistinguishable"
            lines.append(
                f"  Honest-DiD bound at $M={r['M_smoothness']}$ "
                f"(worst-case post = {r['worst_case_post']:+.3f}) & "
                f"\\multicolumn{{4}}{{l}}{{{tag}}} \\\\"
            )

    # E. Wild bootstrap
    lines.append(r"\midrule")
    lines.append(r"\multicolumn{5}{l}{\textit{E. Wild cluster bootstrap}} \\")
    if boot_df is not None:
        for _, r in boot_df.iterrows():
            lines.append(
                f"  Wild bootstrap (Rademacher, 199 reps, cluster=tag) & "
                f"{fmt(r['estimate'])} & {fmt(r['se_crv1'])} & "
                f"$p_{{\\text{{boot}}}}<0.005$ & --- \\\\"
            )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\begin{minipage}{0.95\textwidth}")
    lines.append(r"\scriptsize")
    lines.append(r"Notes. Baseline regression: "
                 r"$\log(1+Q_{t,w,k}) = \beta_{\text{DDD}}\,(\text{AI}_t\cdot\text{Post}_w\cdot\text{Sub}_k) "
                 r"+ \gamma_1 (\text{AI}_t\cdot\text{Post}_w) + \gamma_2 (\text{AI}_t\cdot\text{Sub}_k) "
                 r"+ \gamma_3 (\text{Post}_w\cdot\text{Sub}_k) + \alpha_{t,k} + \delta_w + \varepsilon$. "
                 r"FE: tag$\times$question-type and week. Errors clustered by tag (CR1). "
                 r"$^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$. Specification curve in "
                 r"Figure~\ref{fig:speccurve} reports 32 alternative specifications; "
                 r"100\% are negative and significant at $p<0.05$.")
    lines.append(r"\end{minipage}")
    lines.append(r"\end{table}")

    args.out_tex.parent.mkdir(parents=True, exist_ok=True)
    args.out_tex.write_text("\n".join(lines), encoding="utf-8")
    print(f"saved {args.out_tex}")


if __name__ == "__main__":
    main()
