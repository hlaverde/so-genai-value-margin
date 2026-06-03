"""
Two referee-requested upgrades in one script:

    M7  Cluster-robust inference with CR3 (jackknife) reported as a
        complement to CR1.  pyfixest supports both via vcov={"CRV1":...}
        and vcov={"CRV3":...}; the latter is the Bell--McCaffrey-style
        jackknife alternative that referees expect when n_cluster is at
        the lower end (here n_tag = 100).

    M2  HonestDiD Delta-RM bounds with the *full* event-study
        variance-covariance matrix, not the diagonal approximation.
        We refit the event study with cluster-robust VCV (CR1 by tag),
        extract the full sigma, drop the omitted bin, and feed the
        result to honestdid.

Outputs:
    outputs/models/cr3_robustness_results.csv
    outputs/models/honestdid_fullvcv_results.csv
    outputs/tables/table_cr3_baseline.{tex,csv}
    outputs/tables/table_honestdid_fullvcv.{tex,csv}
    outputs/figures/fig_honestdid_fullvcv.{pdf,png}
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
MODELS_DIR = OUTPUTS_DIR / "models"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"
for _d in (MODELS_DIR, TABLES_DIR, FIGURES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

AI_VAR = "ai_answerability_structural"
PANEL = PROCESSED_DIR / "stackoverflow_question_type_master_panel.csv"


# ----- M7: CR3 (jackknife) cluster-robust ----------------------------------
def prep_baseline_panel() -> pd.DataFrame:
    df = pd.read_csv(PANEL)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["tag_qtype"] = df["tag"].astype(str) + "::" + df["question_type"].astype(str)
    df["week_id"] = df["week_start"].dt.strftime("%Y-%m-%d")
    df["sub"] = df["substitutable_type"].astype(int)
    df["ai"] = df[AI_VAR].astype(float)
    df["post"] = (df["week_start"] >= CHATGPT_RELEASE).astype(int)
    df["ai_post"] = df["ai"] * df["post"]
    df["ai_sub"] = df["ai"] * df["sub"]
    df["post_sub"] = df["post"] * df["sub"]
    df["ai_post_sub"] = df["ai"] * df["post"] * df["sub"]
    df["log_questions_p1"] = np.log1p(df["questions"].astype(float))
    return df


def fit_baseline(df: pd.DataFrame, vcov_spec):
    return pf.feols(
        "log_questions_p1 ~ ai_post + ai_sub + post_sub + ai_post_sub "
        "| tag_qtype + week_id",
        data=df, vcov=vcov_spec,
    )


def extract_triple(model):
    key = "ai_post_sub"
    coefs = model.coef(); ses = model.se(); pvals = model.pvalue()
    ci = model.confint()
    low_col = "2.5%" if "2.5%" in ci.columns else "2.5 %"
    high_col = "97.5%" if "97.5%" in ci.columns else "97.5 %"
    return {
        "beta": float(coefs[key]),
        "se": float(ses[key]),
        "t": float(coefs[key] / ses[key]),
        "p": float(pvals[key]),
        "ci_low": float(ci.loc[key, low_col]),
        "ci_high": float(ci.loc[key, high_col]),
        "n_obs": int(model._N),
    }


def run_cr3() -> pd.DataFrame:
    df = prep_baseline_panel()
    print(f"[CR3] panel: {len(df):,} rows")
    rows = []
    for label, spec in [
        ("CR1 (Liang-Zeger, baseline)", {"CRV1": "tag"}),
        ("CR3 (jackknife, n_cluster=100)", {"CRV3": "tag"}),
    ]:
        print(f"  fitting {label} ...")
        m = fit_baseline(df, spec)
        rows.append({"spec": label, **extract_triple(m)})
        print(f"    beta={rows[-1]['beta']:.4f}  SE={rows[-1]['se']:.4f}  "
              f"p={rows[-1]['p']:.4f}  CI=[{rows[-1]['ci_low']:.3f}, "
              f"{rows[-1]['ci_high']:.3f}]")
    out = pd.DataFrame(rows)
    out.to_csv(MODELS_DIR / "cr3_robustness_results.csv", index=False)

    # Latex table
    lines = [
        r"\begin{table}[ht]", r"\centering",
        r"\caption{Baseline DDD coefficient under CR1 (Liang--Zeger) and "
        r"CR3 (jackknife) cluster-robust inference, with tag as the "
        r"cluster variable ($n_{\text{tag}} = 100$). CR3 is the "
        r"jackknife-style alternative recommended when the number of "
        r"clusters is at the lower end of the asymptotic regime.}",
        r"\label{tab:cr3_baseline}",
        r"\small",
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Specification & $\hat\beta_{DDD}$ & SE & $t$ & $p$ & 95\% CI \\",
        r"\midrule",
    ]
    for _, r in out.iterrows():
        ci = f"[{r['ci_low']:.3f}, {r['ci_high']:.3f}]"
        lines.append(
            f"{r['spec']} & {r['beta']:.4f} & {r['se']:.4f} & "
            f"{r['t']:.2f} & {r['p']:.4f} & {ci} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    (TABLES_DIR / "table_cr3_baseline.tex").write_text(
        "\n".join(lines), encoding="utf-8")
    out.to_csv(TABLES_DIR / "table_cr3_baseline.csv", index=False)
    return out


# ----- M2: HonestDiD with full sigma --------------------------------------
def fit_event_study(df: pd.DataFrame):
    """
    Quarterly event-study with relative-time dummies bin_-12..bin_+8,
    omitting bin_-1.  Returns a fitted feols model with cluster-robust
    (CR1 by tag) VCV that we can extract entirely.
    """
    work = df.copy()
    # weeks_from_chatgpt is already in master panel
    weeks_from = work["weeks_from_chatgpt"].astype(int)
    # quarterly bins
    bin_idx = (weeks_from + 7) // 13  # so that bin 0 starts at week 0 (roughly)
    work["bin"] = bin_idx
    work["bin"] = work["bin"].clip(lower=-12, upper=8)
    # interact ai*sub with each bin dummy except bin=-1 (reference)
    work["tag_qtype"] = work["tag"].astype(str) + "::" + work["question_type"].astype(str)
    work["week_id"] = work["week_start"].dt.strftime("%Y-%m-%d")
    work["log_questions_p1"] = np.log1p(work["questions"].astype(float))
    work["ai_sub"] = work["ai"] * work["sub"]
    # build relative-time interaction dummies
    bin_values = sorted(work["bin"].unique())
    bin_values = [b for b in bin_values if b != -1]
    for b in bin_values:
        col = f"d_b{b:+d}".replace("+", "p").replace("-", "m")
        work[col] = (work["bin"] == b).astype(int) * work["ai_sub"]
    int_cols = [c for c in work.columns if c.startswith("d_b")]
    rhs = " + ".join(int_cols)
    formula = (f"log_questions_p1 ~ {rhs} | tag_qtype + week_id")
    print(f"[ES] fitting event study with {len(int_cols)} interaction dummies ...")
    m = pf.feols(formula, data=work, vcov={"CRV1": "tag"})
    return m, bin_values, int_cols


def run_honestdid_fullvcv() -> dict:
    df = prep_baseline_panel()
    m, bin_values, int_cols = fit_event_study(df)
    # Extract betahat ordered as numPrePeriods then numPostPeriods
    pre_bins = sorted([b for b in bin_values if b < -1])
    post_bins = sorted([b for b in bin_values if b >= 0])
    print(f"[honestdid] pre bins: {pre_bins}")
    print(f"[honestdid] post bins: {post_bins}")
    ordered_cols = ([f"d_b{b:+d}".replace("+", "p").replace("-", "m") for b in pre_bins]
                    + [f"d_b{b:+d}".replace("+", "p").replace("-", "m") for b in post_bins])
    coefs = m.coef()
    betahat = np.array([float(coefs[c]) for c in ordered_cols])
    # Full VCV
    try:
        sigma = m._vcov.copy() if hasattr(m, "_vcov") else m.vcov_matrix.copy()
    except Exception:
        sigma = None
    if sigma is None:
        # Fallback: get via .se() squared and assume diagonal (degraded)
        ses = m.se()
        diag = np.array([float(ses[c])**2 for c in ordered_cols])
        sigma_sub = np.diag(diag)
        print("[honestdid] WARNING: falling back to diagonal sigma")
    else:
        # sigma is a DataFrame indexed by all coef names; extract submatrix
        if isinstance(sigma, pd.DataFrame):
            sigma_sub = sigma.loc[ordered_cols, ordered_cols].to_numpy()
        else:
            # numpy array; we need ordering from m._coefnames
            coef_names = list(coefs.index)
            idx = [coef_names.index(c) for c in ordered_cols]
            sigma_sub = sigma[np.ix_(idx, idx)]
        print(f"[honestdid] full sigma shape: {sigma_sub.shape}")

    numPre = len(pre_bins)
    numPost = len(post_bins)

    orig = hd.constructOriginalCS(
        betahat=betahat, sigma=sigma_sub,
        numPrePeriods=numPre, numPostPeriods=numPost,
    )
    if hasattr(orig, "iloc"):
        orig_lb = float(orig["lb"].iloc[0])
        orig_ub = float(orig["ub"].iloc[0])
    else:
        orig_lb = float(orig["lb"]); orig_ub = float(orig["ub"])

    print(f"[honestdid] Original CI (full sigma): [{orig_lb:.4f}, {orig_ub:.4f}]")

    Mbarvec = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    print(f"[honestdid] running Delta-RM with Mbarvec={Mbarvec.tolist()} (full sigma) ...")
    sens = hd.createSensitivityResults_relativeMagnitudes(
        betahat=betahat, sigma=sigma_sub,
        numPrePeriods=numPre, numPostPeriods=numPost,
        Mbarvec=Mbarvec, method="C-LF", gridPoints=200,
    )
    print(sens)

    # Save & figure
    sens.to_csv(MODELS_DIR / "honestdid_fullvcv_results.csv", index=False)

    # Find breakdown M (smallest Mbar at which CI contains 0)
    breakdown = None
    for _, row in sens.iterrows():
        if row["lb"] <= 0 <= row["ub"]:
            breakdown = float(row["Mbar"]); break
    print(f"[honestdid] breakdown M_bar = {breakdown}")

    # LaTeX
    lines = [
        r"\begin{table}[ht]", r"\centering",
        r"\caption{HonestDiD $\Delta^{\text{RM}}$ bounds with the full "
        r"cluster-robust variance-covariance matrix of the event-study "
        r"coefficients (refit at the tag $\times$ question-type cell). "
        r"The full-VCV bound complements the diagonal approximation used "
        r"in \S\ref{ssec:id_honest_did}.}",
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
            f"$\\bar M = {float(row['Mbar']):.1f}$ & {float(row['lb']):.4f} & "
            f"{float(row['ub']):.4f} & {status} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    (TABLES_DIR / "table_honestdid_fullvcv.tex").write_text(
        "\n".join(lines), encoding="utf-8")

    # Figure
    fig, ax = plt.subplots(figsize=(7, 3.8), dpi=200)
    x = sens["Mbar"].astype(float).values
    lb = sens["lb"].astype(float).values
    ub = sens["ub"].astype(float).values
    ax.fill_between(x, lb, ub, alpha=0.25, color="#1a1a1a",
                    label=r"Robust 95\% CI ($\Delta^{\rm RM}$, full $\Sigma$)")
    ax.plot(x, lb, color="#1a1a1a", linewidth=1.0)
    ax.plot(x, ub, color="#1a1a1a", linewidth=1.0)
    ax.axhline(0, color="red", linestyle="--", linewidth=0.8,
               label="zero")
    if breakdown is not None:
        ax.axvline(breakdown, color="grey", linestyle=":",
                   label=fr"breakdown $\bar M={breakdown:.1f}$")
    ax.set_xlabel(r"$\bar M$ (relative-magnitude bound)")
    ax.set_ylabel("Average post-period CI bound")
    ax.set_title("HonestDiD $\\Delta^{\\rm RM}$ sensitivity bounds (full VCV)",
                 fontsize=10)
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_honestdid_fullvcv.pdf", bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig_honestdid_fullvcv.png", bbox_inches="tight")
    plt.close(fig)

    return {"orig_lb": orig_lb, "orig_ub": orig_ub, "breakdown": breakdown,
            "numPre": numPre, "numPost": numPost}


def main():
    print(f"[main] start {datetime.now().isoformat(timespec='seconds')}")
    cr3 = run_cr3()
    print("\n" + "="*60 + "\n")
    res = run_honestdid_fullvcv()
    print(f"\n[main] honestdid full-VCV breakdown M_bar = {res['breakdown']}")
    print(f"[main] done {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
