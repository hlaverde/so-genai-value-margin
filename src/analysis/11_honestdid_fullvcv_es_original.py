"""
HonestDiD Delta-RM bounds using the FULL cluster-robust VCV of the
event-study coefficients from the *original* paper-v7 spec
(src/models/event_study_ddd_question_type.py).

This is the replacement for the diagonal-VCV implementation referenced
in the paper.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import honestdid as hd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyfixest as pf

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.paths import OUTPUTS_DIR, PROCESSED_DIR  # noqa: E402

CHATGPT_RELEASE = pd.Timestamp("2022-11-30")
BIN_WEEKS = 13
ANSWERABILITY = "ai_answerability_zscore"  # matches event_study script
PANEL = PROCESSED_DIR / "stackoverflow_question_type_master_panel.csv"
MODELS_DIR = OUTPUTS_DIR / "models"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"
for _d in (MODELS_DIR, TABLES_DIR, FIGURES_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def assign_bin(week: pd.Timestamp) -> int:
    days_diff = (week - CHATGPT_RELEASE).days
    weeks = days_diff // 7
    return weeks // BIN_WEEKS


def bin_name(b: int) -> str:
    return f"aisub_bn{abs(b)}" if b < 0 else f"aisub_bp{b}"


def fit_event_study():
    df = pd.read_csv(PANEL)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["sub"] = df["substitutable_type"].astype(int)
    df["ai"] = df[ANSWERABILITY]
    df["ai_sub"] = df["ai"] * df["sub"]
    df["bin"] = df["week_start"].apply(assign_bin)
    df["week_id"] = df["week_start"].astype(str)
    omit = -1
    bins = sorted(df["bin"].unique())
    for b in bins:
        if b == omit:
            continue
        df[bin_name(b)] = df["ai_sub"] * (df["bin"] == b).astype(int)
    interaction_terms = [bin_name(b) for b in bins if b != omit]
    formula = (f"log_questions_p1 ~ {' + '.join(interaction_terms)} "
               f"| tag_qtype + week_id")
    print(f"[ES] fitting {len(interaction_terms)} bin interactions ...")
    fit = pf.feols(formula, data=df, vcov={"CRV1": "tag"})
    return fit, bins, omit


def get_full_vcov(fit) -> tuple[np.ndarray, list[str]]:
    """Extract the full cluster-robust VCV matrix from a pyfixest fit."""
    # pyfixest stores _vcov as an attribute (numpy array indexed by _coefnames)
    if hasattr(fit, "_vcov") and fit._vcov is not None:
        vcov = np.asarray(fit._vcov)
    elif hasattr(fit, "vcov_matrix"):
        vcov = np.asarray(fit.vcov_matrix)
    else:
        raise RuntimeError("Cannot find VCV matrix on fit object")
    coef_names = list(fit.coef().index)
    return vcov, coef_names


def main() -> None:
    print(f"[main] start {datetime.now().isoformat(timespec='seconds')}")
    fit, bins, omit = fit_event_study()
    coefs = fit.coef()
    print(f"[ES] {len(coefs)} fitted coefficients")

    # Get VCV and order
    vcov, coef_names = get_full_vcov(fit)
    print(f"[ES] VCV shape: {vcov.shape}")
    print(f"[ES] coef names (first 6): {coef_names[:6]}")

    pre_bins = sorted([b for b in bins if b < omit])  # b < -1
    post_bins = sorted([b for b in bins if b >= 0])
    print(f"[ES] pre bins (excluding omit -1): {pre_bins}")
    print(f"[ES] post bins: {post_bins}")

    ordered_names = ([bin_name(b) for b in pre_bins]
                     + [bin_name(b) for b in post_bins])
    available = [n for n in ordered_names if n in coef_names]
    missing = set(ordered_names) - set(available)
    if missing:
        print(f"[ES] WARNING missing coefs: {missing}")
    ordered_names = available
    idx = [coef_names.index(n) for n in ordered_names]
    sigma_sub = vcov[np.ix_(idx, idx)]
    betahat = np.array([float(coefs[n]) for n in ordered_names])
    numPre = sum(1 for b in pre_bins if bin_name(b) in available)
    numPost = sum(1 for b in post_bins if bin_name(b) in available)
    print(f"[ES] betahat length: {len(betahat)}; sigma {sigma_sub.shape}")
    print(f"[ES] numPre={numPre}, numPost={numPost}")
    print(f"[ES] betahat: {betahat.round(4).tolist()}")
    print(f"[ES] sigma diagonal (sqrt -> SE): "
          f"{np.sqrt(np.diag(sigma_sub)).round(4).tolist()}")

    # Original CI (no relaxation)
    orig = hd.constructOriginalCS(
        betahat=betahat, sigma=sigma_sub,
        numPrePeriods=numPre, numPostPeriods=numPost,
    )
    if hasattr(orig, "iloc"):
        orig_lb = float(orig["lb"].iloc[0]); orig_ub = float(orig["ub"].iloc[0])
    else:
        orig_lb = float(orig["lb"]); orig_ub = float(orig["ub"])
    print(f"[honestdid] Original CI (full sigma): "
          f"[{orig_lb:.4f}, {orig_ub:.4f}]")

    # Delta-RM bounds
    Mbarvec = np.array([0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0])
    print(f"[honestdid] running Delta-RM with full sigma, Mbarvec={Mbarvec.tolist()} ...")
    sens = hd.createSensitivityResults_relativeMagnitudes(
        betahat=betahat, sigma=sigma_sub,
        numPrePeriods=numPre, numPostPeriods=numPost,
        Mbarvec=Mbarvec, method="C-LF", gridPoints=200,
    )
    print(sens)

    sens.to_csv(MODELS_DIR / "honestdid_fullvcv_es_original_results.csv",
                index=False)

    breakdown = None
    for _, row in sens.iterrows():
        if row["lb"] <= 0 <= row["ub"]:
            breakdown = float(row["Mbar"]); break
    print(f"\n[honestdid] BREAKDOWN M_bar (full sigma) = {breakdown}")

    # Build LaTeX
    lines = [
        r"\begin{table}[ht]", r"\centering",
        r"\caption{HonestDiD $\Delta^{\text{RM}}$ sensitivity bounds "
        r"with the \emph{full} cluster-robust variance-covariance matrix "
        r"of the event-study coefficients. Computed by refitting the "
        r"original quarterly event study "
        r"(\S\ref{ssec:dynamics_event}) with CR1 (Liang--Zeger) "
        r"clustering on tag and extracting the full $\Sigma$. Robust "
        r"95\% confidence intervals reported for each value of the "
        r"relative-magnitude bound $\bar M$.}",
        r"\label{tab:honestdid_fullvcv}",
        r"\small \setlength{\tabcolsep}{6pt}",
        r"\begin{tabular}{lrrl}",
        r"\toprule",
        r"$\bar M$ & Robust LB & Robust UB & Status \\",
        r"\midrule",
        f"Original (no relaxation) & {orig_lb:.4f} & {orig_ub:.4f} & "
        f"{'excludes 0' if not (orig_lb <= 0 <= orig_ub) else 'contains 0'} \\\\",
    ]
    for _, row in sens.iterrows():
        status = "contains 0" if row["lb"] <= 0 <= row["ub"] else "excludes 0"
        lines.append(
            f"$\\bar M = {float(row['Mbar']):.2f}$ & {float(row['lb']):.4f} & "
            f"{float(row['ub']):.4f} & {status} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    (TABLES_DIR / "table_honestdid_fullvcv.tex").write_text(
        "\n".join(lines), encoding="utf-8")
    print(f"saved {TABLES_DIR / 'table_honestdid_fullvcv.tex'}")

    # Figure
    fig, ax = plt.subplots(figsize=(7, 3.8), dpi=200)
    x = sens["Mbar"].astype(float).values
    lb = sens["lb"].astype(float).values
    ub = sens["ub"].astype(float).values
    ax.fill_between(x, lb, ub, alpha=0.25, color="#1a1a1a",
                    label=r"Robust 95\% CI ($\Delta^{\rm RM}$, full $\Sigma$)")
    ax.plot(x, lb, color="#1a1a1a", linewidth=1.0)
    ax.plot(x, ub, color="#1a1a1a", linewidth=1.0)
    ax.axhline(0, color="red", linestyle="--", linewidth=0.8, label="zero")
    if breakdown is not None:
        ax.axvline(breakdown, color="grey", linestyle=":",
                   label=fr"breakdown $\bar M={breakdown:.2f}$")
    ax.set_xlabel(r"$\bar M$ (relative-magnitude bound)")
    ax.set_ylabel("Average post-period CI bound")
    ax.set_title(r"HonestDiD $\Delta^{\rm RM}$ bounds (full VCV)", fontsize=10)
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_honestdid_fullvcv.pdf", bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig_honestdid_fullvcv.png", bbox_inches="tight")
    plt.close(fig)
    print(f"saved {FIGURES_DIR / 'fig_honestdid_fullvcv.pdf'}")

    print(f"\n[main] done {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
