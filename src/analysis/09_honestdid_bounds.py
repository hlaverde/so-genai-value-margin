"""
HonestDiD bounds for the quarterly event-study (full package
implementation, replacing the prior bespoke implementation).

Loads the existing event-study coefficients and standard errors
(outputs/tables/event_study_ddd_question_type_quarterly.csv), builds
a diagonal sigma (independence approximation; the full off-diagonal
covariance is not stored), and runs:

  (1) constructOriginalCS         -> unadjusted post-period CI
  (2) createSensitivityResults_RM -> Delta-RM bounds across Mbar grid

For each Mbar in the grid, the robust CI is reported and the smallest
Mbar at which the robust CI contains zero is identified.

Outputs:
    outputs/models/honestdid_bounds.csv
    outputs/tables/table_honestdid_bounds.{tex,csv}
    outputs/figures/fig_honestdid_bounds.{pdf,png}
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import honestdid as hd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.paths import OUTPUTS_DIR  # noqa: E402

EVENT_STUDY_CSV = (
    OUTPUTS_DIR / "tables" / "event_study_ddd_question_type_quarterly.csv"
)
MODELS_DIR = OUTPUTS_DIR / "models"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"
for _d in (MODELS_DIR, TABLES_DIR, FIGURES_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def main() -> None:
    print(f"[main] start {datetime.now().isoformat(timespec='seconds')}")
    df = pd.read_csv(EVENT_STUDY_CSV)
    print(f"[main] loaded {len(df)} bins from {EVENT_STUDY_CSV.name}")

    # Keep only rows with a numeric estimate that is NOT the omitted (-1)
    # bin (HonestDiD requires the omitted period to be implicit, i.e., the
    # last pre-period coefficient is omitted internally).
    df = df.dropna(subset=["estimate", "std_err"])
    df = df[df["std_err"] > 0].reset_index(drop=True)
    df = df.sort_values("bin").reset_index(drop=True)

    pre = df[df["is_pre"] == True].reset_index(drop=True)  # noqa: E712
    post = df[df["is_pre"] == False].reset_index(drop=True)  # noqa: E712
    print(f"[main] pre bins (non-omitted): {len(pre)}")
    print(f"[main] post bins: {len(post)}")

    # HonestDiD expects betahat to include pre and post; the package
    # treats the period just before the cutoff (omitted) as period 0.
    betahat = np.concatenate([pre["estimate"].values, post["estimate"].values])
    sigma = np.diag(
        np.concatenate([pre["std_err"].values, post["std_err"].values]) ** 2
    )
    numPrePeriods = len(pre)
    numPostPeriods = len(post)
    print(f"[main] betahat length {len(betahat)}; sigma {sigma.shape}")
    print(f"[main] numPrePeriods={numPrePeriods}, numPostPeriods={numPostPeriods}")

    # Original CI (unadjusted) ---------------------------------------------
    orig = hd.constructOriginalCS(
        betahat=betahat,
        sigma=sigma,
        numPrePeriods=numPrePeriods,
        numPostPeriods=numPostPeriods,
    )
    print(f"[main] constructOriginalCS returned {type(orig).__name__}")
    print(orig)
    # Normalise to scalars
    if hasattr(orig, "iloc"):
        orig_lb = float(orig["lb"].iloc[0])
        orig_ub = float(orig["ub"].iloc[0])
    elif isinstance(orig, dict):
        v_lb = orig["lb"]
        v_ub = orig["ub"]
        orig_lb = float(v_lb.iloc[0] if hasattr(v_lb, "iloc") else v_lb)
        orig_ub = float(v_ub.iloc[0] if hasattr(v_ub, "iloc") else v_ub)
    else:
        orig_lb = float(orig[0]); orig_ub = float(orig[1])
    print(f"[main] Original (pooled post) CI: lb={orig_lb:.4f}, ub={orig_ub:.4f}")

    # Delta-RM (relative magnitudes) bounds --------------------------------
    # Coarser grid + fewer grid points for tractability; refines later if
    # needed.  The bound is monotone in Mbar so coarse-grid identification
    # of the breakdown M-bar is acceptable for the discussion in the paper.
    Mbarvec = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    print(f"[main] running Delta-RM with Mbarvec={Mbarvec.tolist()} ...")
    sens = hd.createSensitivityResults_relativeMagnitudes(
        betahat=betahat,
        sigma=sigma,
        numPrePeriods=numPrePeriods,
        numPostPeriods=numPostPeriods,
        Mbarvec=Mbarvec,
        method="C-LF",
        gridPoints=200,
    )
    print(f"[main] sensitivity returned type {type(sens).__name__}")
    if isinstance(sens, pd.DataFrame):
        sens_df = sens
    else:
        # Older API returns dict-of-lists
        sens_df = pd.DataFrame(sens)
    sens_df = sens_df.reset_index(drop=True)
    print(sens_df)

    # Identify smallest Mbar at which CI contains zero
    contains_zero = (sens_df["lb"] <= 0) & (sens_df["ub"] >= 0)
    if contains_zero.any():
        Mbar_breakdown = float(sens_df.loc[contains_zero, "Mbar"].min())
    else:
        Mbar_breakdown = float("inf")
    print(f"\n[main] Mbar breakdown (smallest Mbar at which 0 in CI): "
          f"{Mbar_breakdown}")

    # Build a tidy output table including original CI
    orig_row = pd.DataFrame([{
        "Mbar": "Original",
        "lb": orig_lb,
        "ub": orig_ub,
        "contains_zero": (orig_lb <= 0 <= orig_ub),
    }])
    grid_rows = sens_df.assign(
        contains_zero=(sens_df["lb"] <= 0) & (sens_df["ub"] >= 0),
    )[["Mbar", "lb", "ub", "contains_zero"]]
    tidy = pd.concat([orig_row, grid_rows], ignore_index=True)
    tidy.to_csv(MODELS_DIR / "honestdid_bounds.csv", index=False)
    tidy.to_csv(TABLES_DIR / "table_honestdid_bounds.csv", index=False)

    # LaTeX table
    lines = [
        r"\begin{table}[ht]", r"\centering",
        r"\caption{HonestDiD pre-trend sensitivity bounds "
        r"\citep{rambachan2023honest}, $\Delta^{\text{RM}}$ class. "
        r"For each value of $\bar{M}$ (the relative magnitude bound), "
        r"the table reports the robust 95\% confidence set for the "
        r"average post-period treatment effect. The breakdown $\bar{M}$ "
        f"is approximately {Mbar_breakdown}, the smallest relative "
        r"magnitude at which the post-period effect becomes "
        r"statistically indistinguishable from zero. Implemented with "
        r"\texttt{honestdid} 0.1.1 (Python port).}",
        r"\label{tab:honestdid_bounds}",
        r"\small \setlength{\tabcolsep}{6pt}",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"$\bar{M}$ & Lower bound & Upper bound & Contains 0? \\",
        r"\midrule",
    ]
    for _, r in tidy.iterrows():
        mbar = r["Mbar"] if isinstance(r["Mbar"], str) else f"{r['Mbar']:.2f}"
        cz = "Yes" if r["contains_zero"] else "No"
        lines.append(f"{mbar} & {r['lb']:.4f} & {r['ub']:.4f} & {cz} \\\\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    (TABLES_DIR / "table_honestdid_bounds.tex").write_text(
        "\n".join(lines), encoding="utf-8")

    # Figure: CI bounds vs Mbar
    fig, ax = plt.subplots(figsize=(7.5, 4.0), dpi=200)
    grid = sens_df.copy()
    ax.fill_between(grid["Mbar"], grid["lb"], grid["ub"],
                    color="#cccccc", alpha=0.5, label=r"Robust 95\% CI")
    ax.plot(grid["Mbar"], grid["lb"], color="#444444", lw=1)
    ax.plot(grid["Mbar"], grid["ub"], color="#444444", lw=1)
    ax.axhline(0, color="#000000", linestyle="--", linewidth=0.8)
    if np.isfinite(Mbar_breakdown):
        ax.axvline(Mbar_breakdown, color="#9c2a2a", linestyle=":", lw=1.5,
                   label=f"Breakdown $\\bar M = {Mbar_breakdown:.2f}$")
    ax.set_xlabel(r"Relative-magnitude bound $\bar M$")
    ax.set_ylabel(r"Robust 95\% CI on post-period effect")
    ax.set_title("HonestDiD pre-trend sensitivity (Delta-RM)", fontsize=10)
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(axis="y", linestyle=":", linewidth=0.5, alpha=0.6)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_honestdid_bounds.pdf",
                bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig_honestdid_bounds.png",
                bbox_inches="tight")
    plt.close(fig)

    print(f"\n[main] outputs written")
    print(f"[main] done {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
