"""Conjunto de robusteces solicitadas por referees de Research Policy.

Incluye:
    (a) Baseline con ai_answerability_structural (en lugar de zscore).
    (b) Honest DiD bounds estilo Rambachan-Roth (2023): cuánta violación
        del paralelismo en la interacción es consistente con que el
        efecto causal post sea no nulo.
    (c) Copilot como placebo positivo (cutoff = 2022-06-21) y como
        co-shock conjunto con ChatGPT.
    (d) Rolling placebos: distribución completa de coeficientes
        DDD asumiendo cutoffs falsos cada 4 semanas en 2020-2022.
    (e) Specification curve: 20+ specs ordenadas por estimate.

Salidas en outputs/tables/ y outputs/figures/.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf
import matplotlib.pyplot as plt


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")
COPILOT_RELEASE = pd.Timestamp("2022-06-21")  # General availability


# ---------- core helper ---------- #
def fit_ddd(df, ai_col, post_col="post"):
    df = df.copy()
    df["sub"] = df["substitutable_type"].astype(int)
    df["ai"] = df[ai_col]
    df["ai_post"] = df["ai"] * df[post_col]
    df["ai_sub"] = df["ai"] * df["sub"]
    df["post_sub"] = df[post_col] * df["sub"]
    df["ai_post_sub"] = df["ai"] * df[post_col] * df["sub"]
    df["week_id"] = df["week_start"].astype(str)
    formula = (
        "log_questions_p1 ~ ai_post + ai_sub + post_sub + ai_post_sub "
        "| tag_qtype + week_id"
    )
    fit = pf.feols(formula, data=df, vcov={"CRV1": "tag"})
    return {
        "estimate": float(fit.coef()["ai_post_sub"]),
        "se": float(fit.se()["ai_post_sub"]),
        "p": float(fit.pvalue()["ai_post_sub"]),
        "n": int(fit._N),
    }


# ---------- (a) Structural baseline ---------- #
def structural_baseline(panel, out_dir):
    rows = []
    for ai_col in [
        "ai_answerability_structural",
        "ai_answerability_zscore",
        "ai_answerability_pca",
        "ai_answerability_quantile",
    ]:
        panel_ = panel.copy()
        panel_["post"] = (panel_["week_start"] >= CHATGPT_RELEASE).astype(int)
        r = fit_ddd(panel_, ai_col)
        r["ai_measure"] = ai_col
        r["is_baseline"] = ai_col == "ai_answerability_structural"
        rows.append(r)
        print(f"  {ai_col:>32s}: DDD = {r['estimate']:+.4f} (SE {r['se']:.4f}, p={r['p']:.3g})")
    out = pd.DataFrame(rows)
    out_csv = out_dir / "rp_structural_baseline.csv"
    out.to_csv(out_csv, index=False)
    print(f"saved {out_csv}\n")
    return out


# ---------- (b) Honest DiD bounds (smoothness restriction) ---------- #
def honest_did_bounds(panel, ai_col, out_dir):
    """Approximación al estilo Rambachan-Roth (2023, ReStud).

    Estimamos el event-study a frecuencia 13-semanas (igual a la
    figura del paper). Asumimos que la magnitud máxima de la
    desviación del paralelismo en cada bin post es a lo sumo M veces
    la mayor magnitud observada en bins pre. Calculamos β_DDD
    promedio post bajo distintos valores de M:
        M = 0  → paralelismo perfecto (no se permite ningún sesgo)
        M = 1  → permite que cualquier bin post tenga el mismo desvío
                 máximo que la mayor anomalía pre
        M = 2  → permite el doble
    Si M*(max pre coef abs) >= |average post coef|, entonces el
    efecto post no es distinguible de extrapolación de pre-trends.
    """
    df = panel.copy()
    df["sub"] = df["substitutable_type"].astype(int)
    df["ai"] = df[ai_col]
    df["ai_sub"] = df["ai"] * df["sub"]
    df["week_id"] = df["week_start"].astype(str)

    # Bins de 13 semanas
    BIN_WEEKS = 13
    df["bin"] = ((df["week_start"] - CHATGPT_RELEASE).dt.days // 7) // BIN_WEEKS
    bins = sorted(df["bin"].unique())
    omit = -1
    def bin_name(b): return f"aisub_bn{abs(b)}" if b < 0 else f"aisub_bp{b}"
    for b in bins:
        if b == omit:
            continue
        df[bin_name(b)] = df["ai_sub"] * (df["bin"] == b).astype(int)
    terms = [bin_name(b) for b in bins if b != omit]
    formula = f"log_questions_p1 ~ {' + '.join(terms)} | tag_qtype + week_id"
    fit = pf.feols(formula, data=df, vcov={"CRV1": "tag"})

    coefs = fit.coef()
    ses = fit.se()
    rows = []
    for b in bins:
        if b == omit:
            rows.append({"bin": b, "coef": 0.0, "se": 0.0, "is_pre": True})
            continue
        nm = bin_name(b)
        if nm not in coefs.index:
            continue
        rows.append({"bin": b, "coef": float(coefs[nm]), "se": float(ses[nm]),
                     "is_pre": b < 0})
    es_df = pd.DataFrame(rows).sort_values("bin").reset_index(drop=True)

    pre = es_df[es_df["is_pre"] & (es_df["bin"] != omit)]
    post = es_df[~es_df["is_pre"]]
    max_abs_pre = float(pre["coef"].abs().max())
    mean_post = float(post["coef"].mean())

    print(f"  Honest DiD: max|pre| = {max_abs_pre:.4f}, mean(post) = {mean_post:.4f}")
    rr_rows = []
    for M in [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]:
        # En el peor caso (worst-case under smoothness M),
        # the true post effect is bounded by post - M*max_abs_pre
        # (signo conservador). Usamos signo del effect observado.
        worst_post = abs(mean_post) - M * max_abs_pre
        breakdown = abs(mean_post) <= M * max_abs_pre
        rr_rows.append({
            "M_smoothness": M,
            "max_abs_pre": max_abs_pre,
            "mean_post_abs": abs(mean_post),
            "worst_case_post": worst_post,
            "indistinguishable_from_extrapolated_trend": breakdown,
        })
    rr = pd.DataFrame(rr_rows)
    out_csv = out_dir / "rp_honest_did_bounds.csv"
    rr.to_csv(out_csv, index=False)
    print(rr.to_string(index=False))
    print(f"saved {out_csv}\n")
    return rr


# ---------- (c) Copilot ---------- #
def copilot_analysis(panel, ai_col, out_dir):
    df = panel.copy()
    df["post_copilot"] = (df["week_start"] >= COPILOT_RELEASE).astype(int)
    df["post_chatgpt"] = (df["week_start"] >= CHATGPT_RELEASE).astype(int)

    rows = []

    # (c1) Copilot solo, en muestra PRE-ChatGPT
    pre = df[df["week_start"] < CHATGPT_RELEASE].copy()
    pre["post"] = (pre["week_start"] >= COPILOT_RELEASE).astype(int)
    if pre["post"].sum() > 100 and (pre["post"] == 0).sum() > 100:
        r = fit_ddd(pre, ai_col)
        r["spec"] = "copilot_only_pre_chatgpt"
        r["cutoff"] = "2022-06-21 (Copilot GA)"
        rows.append(r)
        print(
            f"  Copilot solo (pre-ChatGPT): DDD = {r['estimate']:+.4f} "
            f"(SE {r['se']:.4f}, p={r['p']:.3g})"
        )

    # (c2) Dos shocks: Copilot + ChatGPT
    df["sub"] = df["substitutable_type"].astype(int)
    df["ai"] = df[ai_col]
    df["ai_copilot"] = df["ai"] * df["post_copilot"]
    df["ai_chatgpt"] = df["ai"] * df["post_chatgpt"]
    df["sub_copilot"] = df["sub"] * df["post_copilot"]
    df["sub_chatgpt"] = df["sub"] * df["post_chatgpt"]
    df["ai_sub"] = df["ai"] * df["sub"]
    df["ai_sub_copilot"] = df["ai"] * df["sub"] * df["post_copilot"]
    df["ai_sub_chatgpt"] = df["ai"] * df["sub"] * df["post_chatgpt"]
    df["week_id"] = df["week_start"].astype(str)
    formula = (
        "log_questions_p1 ~ ai_copilot + ai_chatgpt + ai_sub + "
        "sub_copilot + sub_chatgpt + ai_sub_copilot + ai_sub_chatgpt "
        "| tag_qtype + week_id"
    )
    fit = pf.feols(formula, data=df, vcov={"CRV1": "tag"})
    for var in ["ai_sub_copilot", "ai_sub_chatgpt"]:
        if var in fit.coef().index:
            rows.append(
                {
                    "spec": f"dual_shock_{var.replace('ai_sub_','')}",
                    "cutoff": "joint",
                    "estimate": float(fit.coef()[var]),
                    "se": float(fit.se()[var]),
                    "p": float(fit.pvalue()[var]),
                    "n": int(fit._N),
                }
            )
            print(
                f"  Dual-shock [{var}]: DDD = {rows[-1]['estimate']:+.4f} "
                f"(SE {rows[-1]['se']:.4f}, p={rows[-1]['p']:.3g})"
            )

    out = pd.DataFrame(rows)
    out_csv = out_dir / "rp_copilot_analysis.csv"
    out.to_csv(out_csv, index=False)
    print(f"saved {out_csv}\n")
    return out


# ---------- (d) Rolling placebos ---------- #
def rolling_placebos(panel, ai_col, out_dir, step_weeks: int = 4):
    df = panel[panel["week_start"] < CHATGPT_RELEASE].copy()
    start = pd.Timestamp("2020-07-01")
    end = pd.Timestamp("2022-09-01")
    cutoffs = pd.date_range(start, end, freq=f"{step_weeks * 7}D")
    rows = []
    print(f"  rolling placebos: {len(cutoffs)} cutoffs every {step_weeks} weeks")
    for cut in cutoffs:
        sub = df.copy()
        sub["post"] = (sub["week_start"] >= cut).astype(int)
        if sub["post"].mean() in (0.0, 1.0):
            continue
        try:
            r = fit_ddd(sub, ai_col)
            rows.append(
                {"cutoff": cut.strftime("%Y-%m-%d"), **r}
            )
        except Exception as exc:
            print(f"    {cut} skip: {exc}")
    out = pd.DataFrame(rows)
    out_csv = out_dir / "rp_rolling_placebos.csv"
    out.to_csv(out_csv, index=False)
    print(f"saved {out_csv}: {len(out)} rolling placebos\n")
    print(f"  mean placebo coef = {out['estimate'].mean():+.4f}")
    print(f"  pct of placebos < real coef (-0.138): "
          f"{(out['estimate'] < -0.138).mean()*100:.1f}%")

    # Figura
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(out["estimate"], bins=20, color="steelblue", alpha=0.75,
            edgecolor="black")
    ax.axvline(-0.138, color="firebrick", linewidth=2,
               label="Real cutoff coef (-0.138)")
    ax.axvline(0, color="grey", linewidth=0.8, linestyle="--")
    ax.set_xlabel("DDD coefficient")
    ax.set_ylabel("Number of placebo cutoffs")
    ax.set_title(
        f"Rolling placebo distribution ({len(out)} fake cutoffs, "
        f"every {step_weeks} weeks, pre-ChatGPT)"
    )
    ax.legend()
    fig.tight_layout()
    out_fig = out_dir.parent / "figures" / "rp_rolling_placebo_distribution.png"
    out_fig.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_fig, dpi=160)
    plt.close(fig)
    print(f"saved {out_fig}\n")
    return out


# ---------- (e) Specification curve ---------- #
def specification_curve(panel, out_dir):
    """Genera ~24 specs combinando: 4 AI measures × samples × outcomes."""
    AI_COLS = [
        "ai_answerability_structural",
        "ai_answerability_zscore",
        "ai_answerability_pca",
        "ai_answerability_quantile",
    ]
    SAMPLES = ["full", "top50", "top75", "iqr_band"]
    OUTCOMES = ["log_questions_p1", "log_unique_users_p1"]

    # Precompute sample subsets
    pre = panel[panel["week_start"] < CHATGPT_RELEASE]
    volume = pre.groupby("tag")["questions"].sum().sort_values(ascending=False)
    top50_tags = set(volume.head(50).index)
    top75_tags = set(volume.head(75).index)
    # IQR band on pre-slope (computed once)
    weekly = (
        pre.groupby(["tag", "week_start"])["questions"].sum().reset_index()
    )
    weekly["log_q"] = np.log1p(weekly["questions"])
    weekly["t"] = ((weekly["week_start"] - weekly["week_start"].min())
                   .dt.days // 7).astype(int)
    from scipy.stats import linregress
    slopes = {}
    for tag, sub in weekly.groupby("tag"):
        if len(sub) >= 10:
            slopes[tag] = linregress(sub["t"], sub["log_q"]).slope
    s = pd.Series(slopes)
    med = s.median()
    iqr = s.quantile(0.75) - s.quantile(0.25)
    iqr_tags = set(s[(s - med).abs() <= iqr].index)

    def get_sample(sample):
        if sample == "full":
            return panel
        if sample == "top50":
            return panel[panel["tag"].isin(top50_tags)]
        if sample == "top75":
            return panel[panel["tag"].isin(top75_tags)]
        if sample == "iqr_band":
            return panel[panel["tag"].isin(iqr_tags)]
        raise ValueError(sample)

    rows = []
    for ai_col in AI_COLS:
        for sample in SAMPLES:
            for outcome in OUTCOMES:
                sub = get_sample(sample).copy()
                sub["post"] = (sub["week_start"] >= CHATGPT_RELEASE).astype(int)
                sub["sub"] = sub["substitutable_type"].astype(int)
                sub["ai"] = sub[ai_col]
                sub["ai_post"] = sub["ai"] * sub["post"]
                sub["ai_sub"] = sub["ai"] * sub["sub"]
                sub["post_sub"] = sub["post"] * sub["sub"]
                sub["ai_post_sub"] = sub["ai"] * sub["post"] * sub["sub"]
                sub["week_id"] = sub["week_start"].astype(str)
                formula = (
                    f"{outcome} ~ ai_post + ai_sub + post_sub + ai_post_sub "
                    "| tag_qtype + week_id"
                )
                try:
                    fit = pf.feols(formula, data=sub, vcov={"CRV1": "tag"})
                    rows.append(
                        {
                            "ai_measure": ai_col.replace("ai_answerability_", ""),
                            "sample": sample,
                            "outcome": outcome,
                            "estimate": float(fit.coef()["ai_post_sub"]),
                            "se": float(fit.se()["ai_post_sub"]),
                            "p": float(fit.pvalue()["ai_post_sub"]),
                            "n": int(fit._N),
                        }
                    )
                except Exception as exc:
                    print(f"    failed {ai_col}/{sample}/{outcome}: {exc}")
    out = pd.DataFrame(rows).sort_values("estimate")
    out_csv = out_dir / "rp_specification_curve.csv"
    out.to_csv(out_csv, index=False)
    print(f"  {len(out)} specs computed")
    print(f"  range: [{out['estimate'].min():+.4f}, {out['estimate'].max():+.4f}]")
    print(f"  share negative: {(out['estimate'] < 0).mean()*100:.0f}%")
    print(f"  share p < 0.05: {(out['p'] < 0.05).mean()*100:.0f}%")
    print(f"saved {out_csv}")

    # Figura specification curve
    fig, axes = plt.subplots(2, 1, figsize=(10, 7),
                             gridspec_kw={"height_ratios": [2, 3]})
    ax = axes[0]
    out_sorted = out.reset_index(drop=True)
    ax.errorbar(range(len(out_sorted)), out_sorted["estimate"],
                yerr=1.96 * out_sorted["se"], fmt="o", color="black",
                ecolor="grey", markersize=4)
    ax.axhline(0, color="grey", linestyle="--", alpha=0.5)
    ax.axhline(-0.138, color="firebrick", linestyle=":", alpha=0.8,
               label="Baseline (z-score) -0.138")
    ax.set_ylabel(r"$\beta_{DDD}$")
    ax.set_title(f"Specification curve ({len(out)} specs, sorted by estimate)")
    ax.set_xticks([])
    ax.legend(loc="lower right", fontsize=8)
    # Panel inferior: factor map
    ax = axes[1]
    factors = pd.DataFrame({
        "spec_id": range(len(out_sorted)),
        "ai_structural": (out_sorted["ai_measure"] == "structural").astype(int),
        "ai_zscore": (out_sorted["ai_measure"] == "zscore").astype(int),
        "ai_pca": (out_sorted["ai_measure"] == "pca").astype(int),
        "ai_quantile": (out_sorted["ai_measure"] == "quantile").astype(int),
        "sample_full": (out_sorted["sample"] == "full").astype(int),
        "sample_top50": (out_sorted["sample"] == "top50").astype(int),
        "sample_top75": (out_sorted["sample"] == "top75").astype(int),
        "sample_iqr": (out_sorted["sample"] == "iqr_band").astype(int),
        "outc_questions": (out_sorted["outcome"] == "log_questions_p1").astype(int),
        "outc_users": (out_sorted["outcome"] == "log_unique_users_p1").astype(int),
    })
    cols = [c for c in factors.columns if c != "spec_id"]
    for i, c in enumerate(cols):
        on = factors[factors[c] == 1]["spec_id"]
        ax.scatter(on, [i] * len(on), s=10, color="steelblue")
    ax.set_yticks(range(len(cols)))
    ax.set_yticklabels(cols, fontsize=8)
    ax.set_xlabel("Specification ID (sorted by estimate)")
    ax.invert_yaxis()
    ax.set_xlim(-1, len(out_sorted))
    ax.set_title("Specification factor map")
    fig.tight_layout()
    out_fig = out_dir.parent / "figures" / "rp_specification_curve.png"
    fig.savefig(out_fig, dpi=160)
    plt.close(fig)
    print(f"saved {out_fig}\n")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--panel", type=Path,
        default=Path("data/processed/stackoverflow_question_type_master_panel.csv"),
    )
    p.add_argument("--out-dir", type=Path, default=Path("outputs/tables"))
    args = p.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    panel = pd.read_csv(args.panel)
    panel["week_start"] = pd.to_datetime(panel["week_start"])

    print("=== (a) Structural baseline ===")
    structural_baseline(panel, args.out_dir)

    print("=== (b) Honest DiD bounds (Rambachan-Roth 2023, simplified) ===")
    honest_did_bounds(panel, "ai_answerability_structural", args.out_dir)

    print("=== (c) Copilot co-shock ===")
    copilot_analysis(panel, "ai_answerability_structural", args.out_dir)

    print("=== (d) Rolling placebos (pre-ChatGPT only) ===")
    rolling_placebos(panel, "ai_answerability_structural", args.out_dir)

    print("=== (e) Specification curve ===")
    specification_curve(panel, args.out_dir)


if __name__ == "__main__":
    main()
