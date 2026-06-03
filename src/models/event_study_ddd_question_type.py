"""Event study triple-diferencia con bins trimestrales (13 semanas).

Estima coeficientes (AI_t · Sub_k) × bin_p para cada periodo p relativo
a ChatGPT, omitiendo el bin justo antes (p = -1). Test conjunto F sobre
los bins pre-tratamiento para chequear pre-trends.

Modelo:
    log(1 + Q_{t,w,k}) =
        Σ_{p≠-1} β_p · (AI_t · Sub_k · 1{w ∈ bin_p})
      + γ_t (FE tag×qtype)
      + δ_w (FE week)
      + ε

H0 pre-trends: β_{-K} = ... = β_{-2} = 0.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf
import matplotlib.pyplot as plt


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")
BIN_WEEKS = 13


def assign_bin(week: pd.Timestamp, bin_weeks: int) -> int:
    days_diff = (week - CHATGPT_RELEASE).days
    # bin -1 cubre las bin_weeks semanas justo antes de cutoff
    weeks = days_diff // 7
    return weeks // bin_weeks


def event_study(
    panel_path: Path,
    out_dir: Path,
    bin_weeks: int = BIN_WEEKS,
    answerability_col: str = "ai_answerability_zscore",
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(panel_path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["sub"] = df["substitutable_type"].astype(int)
    df["ai"] = df[answerability_col]
    df["ai_sub"] = df["ai"] * df["sub"]
    df["bin"] = df["week_start"].apply(lambda w: assign_bin(w, bin_weeks))

    bin_counts = df["bin"].value_counts().sort_index()
    print("bin distribution:")
    for b, n in bin_counts.items():
        sample_week = df.loc[df["bin"] == b, "week_start"].min()
        print(f"  bin={b:+d}: n={n:>6} (first_week={sample_week:%Y-%m-%d})")

    # Omitido: bin = -1 (último bin pretratamiento)
    omit = -1
    df["week_id"] = df["week_start"].astype(str)

    # i(bin, ref=omit) interactuado con ai_sub: nombre seguro para formulaic
    def bin_name(b: int) -> str:
        return f"aisub_bn{abs(b)}" if b < 0 else f"aisub_bp{b}"

    bins = sorted(df["bin"].unique())
    for b in bins:
        if b == omit:
            continue
        df[bin_name(b)] = df["ai_sub"] * (df["bin"] == b).astype(int)

    interaction_terms = [bin_name(b) for b in bins if b != omit]
    formula = f"log_questions_p1 ~ {' + '.join(interaction_terms)} | tag_qtype + week_id"
    print(f"\nFitting {len(interaction_terms)} bin interactions...")
    fit = pf.feols(formula, data=df, vcov={"CRV1": "tag"})

    coefs = fit.coef()
    ses = fit.se()
    ps = fit.pvalue()
    cis = fit.confint()

    out_rows = []
    for b in bins:
        if b == omit:
            out_rows.append(
                {
                    "bin": b,
                    "bin_label": "omit (-1)",
                    "weeks_from_chatgpt_mid": (b * bin_weeks) + bin_weeks // 2,
                    "estimate": 0.0,
                    "std_err": 0.0,
                    "p": np.nan,
                    "ci_lo": 0.0,
                    "ci_hi": 0.0,
                    "is_pre": True,
                }
            )
            continue
        name = bin_name(b)
        if name not in coefs.index:
            continue
        out_rows.append(
            {
                "bin": b,
                "bin_label": f"{b:+d}",
                "weeks_from_chatgpt_mid": (b * bin_weeks) + bin_weeks // 2,
                "estimate": float(coefs[name]),
                "std_err": float(ses[name]),
                "p": float(ps[name]),
                "ci_lo": float(cis.loc[name, "2.5%"]),
                "ci_hi": float(cis.loc[name, "97.5%"]),
                "is_pre": b < 0,
            }
        )
    out_df = pd.DataFrame(out_rows).sort_values("bin").reset_index(drop=True)
    csv_path = out_dir / "event_study_ddd_question_type_quarterly.csv"
    out_df.to_csv(csv_path, index=False)
    print(f"saved {csv_path}")

    # Test F joint sobre bins pre-tratamiento (excluyendo omit)
    pre_terms = [bin_name(b) for b in bins if b < 0 and b != omit]
    if pre_terms:
        wald = fit.wald_test([f"{t}=0" for t in pre_terms])
        try:
            pre_test = {
                "F_or_chi2": float(wald["statistic"]),
                "pvalue": float(wald["pvalue"]),
                "n_restrictions": len(pre_terms),
                "test": "wald",
            }
        except Exception:
            pre_test = {"raw": str(wald)}
    else:
        pre_test = {"note": "no pre-bins available"}
    print(f"\nPre-trends joint test: {pre_test}")
    pd.DataFrame([pre_test]).to_csv(out_dir / "event_study_ddd_pretrend_test.csv", index=False)

    # Figura
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axhline(0, color="grey", linewidth=0.7, linestyle="--")
    ax.axvline(0, color="red", linewidth=0.7, alpha=0.5, label="ChatGPT release")
    pre = out_df[out_df["is_pre"]]
    post = out_df[~out_df["is_pre"]]
    ax.errorbar(
        pre["weeks_from_chatgpt_mid"], pre["estimate"],
        yerr=1.96 * pre["std_err"], fmt="o", color="steelblue", label="pre",
    )
    ax.errorbar(
        post["weeks_from_chatgpt_mid"], post["estimate"],
        yerr=1.96 * post["std_err"], fmt="o", color="firebrick", label="post",
    )
    ax.set_xlabel("Weeks from ChatGPT release (bin midpoint)")
    ax.set_ylabel("Coef: AI × Substitutable × Bin")
    ax.set_title(f"Event study DDD (bins = {bin_weeks} weeks); answer={answerability_col}")
    ax.legend()
    fig.tight_layout()
    fig_path = out_dir.parent / "figures" / "event_study_ddd_question_type_quarterly.png"
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(fig_path, dpi=150)
    plt.close(fig)
    print(f"saved {fig_path}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--panel",
        type=Path,
        default=Path("data/processed/stackoverflow_question_type_master_panel.csv"),
    )
    p.add_argument("--out-dir", type=Path, default=Path("outputs/tables"))
    p.add_argument("--bin-weeks", type=int, default=BIN_WEEKS)
    p.add_argument(
        "--answerability",
        default="ai_answerability_zscore",
    )
    args = p.parse_args()
    event_study(args.panel, args.out_dir, args.bin_weeks, args.answerability)


if __name__ == "__main__":
    main()
