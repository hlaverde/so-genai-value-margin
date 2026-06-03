"""
Three referee-required upgrades in one script:

  P5 HonestDiD Delta-SD bounds (smoothness) in addition to Delta-RM.
  P6 Score-threshold sensitivity of the high-value funnel: re-fit the
     DDD with high_value_score>=k for k in {1,2,3,4,5}.
  P7 Voting-baseline-normalised high-value: rescale post-period score
     by tag-week voting baseline to address the concern that voting
     volume falls post-ChatGPT, depressing scores mechanically.

Outputs:
  outputs/models/honestdid_deltaSD_results.csv
  outputs/models/score_threshold_sensitivity.csv
  outputs/models/voting_normalised_highvalue.csv
  outputs/tables/table_honestdid_deltaSD.tex
  outputs/tables/table_score_threshold_sensitivity.tex
  outputs/tables/table_voting_normalised_highvalue.tex
"""
from __future__ import annotations

import sys
import time
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

from src.paths import OUTPUTS_DIR, PROCESSED_DIR, RAW_DIR  # noqa: E402
from src.data.prepare_stackoverflow_question_type_raw import (  # noqa: E402
    TAG_ALIASES,
    classify_questions,
    source_files,
)

CHATGPT_RELEASE = pd.Timestamp("2022-11-30")
PANEL_WEEK_MIN = pd.Timestamp("2020-01-06")
BIN_WEEKS = 13
ANSWERABILITY = "ai_answerability_zscore"
PANEL = PROCESSED_DIR / "stackoverflow_question_type_master_panel.csv"
RAW_SO = RAW_DIR / "stackoverflow"
AI_REAL = PROCESSED_DIR / "ai_answerability_real.csv"
MODELS = OUTPUTS_DIR / "models"
TABLES = OUTPUTS_DIR / "tables"
FIGURES = OUTPUTS_DIR / "figures"
for _d in (MODELS, TABLES, FIGURES):
    _d.mkdir(parents=True, exist_ok=True)

AI_VAR = "ai_answerability_structural"


# =================== P5: HonestDiD Delta-SD ===========================
def assign_bin(week: pd.Timestamp) -> int:
    days_diff = (week - CHATGPT_RELEASE).days
    return (days_diff // 7) // BIN_WEEKS


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
    fit = pf.feols(formula, data=df, vcov={"CRV1": "tag"})
    return fit, bins, omit


def get_full_vcov(fit):
    if hasattr(fit, "_vcov") and fit._vcov is not None:
        vcov = np.asarray(fit._vcov)
    else:
        vcov = np.asarray(fit.vcov_matrix)
    return vcov, list(fit.coef().index)


def run_p5_honestdid_sd():
    print("\n" + "="*60)
    print("[P5] HonestDiD Delta-SD bounds")
    print("="*60)
    fit, bins, omit = fit_event_study()
    vcov, coef_names = get_full_vcov(fit)
    pre_bins = sorted([b for b in bins if b < omit])
    post_bins = sorted([b for b in bins if b >= 0])
    ordered = ([bin_name(b) for b in pre_bins]
               + [bin_name(b) for b in post_bins])
    idx = [coef_names.index(n) for n in ordered if n in coef_names]
    sigma = vcov[np.ix_(idx, idx)]
    coefs = fit.coef()
    betahat = np.array([float(coefs[n]) for n in ordered if n in coef_names])
    numPre = len(pre_bins)
    numPost = len(post_bins)
    print(f"[P5] betahat length: {len(betahat)}; numPre={numPre}, numPost={numPost}")

    # Delta-SD bounds: smoothness restriction
    # M parameter for ΔSD has different interpretation than ΔRM
    # Sensitivity reports CI as a function of M (curvature bound)
    Mvec = np.array([0.0, 0.01, 0.02, 0.03, 0.05, 0.10])
    print(f"[P5] running Delta-SD with Mvec={Mvec.tolist()} ...")
    try:
        sd = hd.createSensitivityResults(
            betahat=betahat, sigma=sigma,
            numPrePeriods=numPre, numPostPeriods=numPost,
            Mvec=Mvec, method="C-F",
        )
        print(sd)
        sd.to_csv(MODELS / "honestdid_deltaSD_results.csv", index=False)
        # breakdown M
        breakdown = None
        for _, row in sd.iterrows():
            if row["lb"] <= 0 <= row["ub"]:
                breakdown = float(row["M"]); break
        print(f"[P5] Delta-SD breakdown M = {breakdown}")
        # LaTeX
        lines = [
            r"\begin{table}[ht]", r"\centering",
            r"\caption{HonestDiD $\Delta^{\text{SD}}$ (smoothness) "
            r"sensitivity bounds, complementing the $\Delta^{\text{RM}}$ "
            r"bounds of Table~\ref{tab:honestdid_fullvcv}. Under "
            r"$\Delta^{\text{SD}}$ the post-period deviation from "
            r"parallel trends is constrained to vary smoothly across "
            r"adjacent periods (second-difference bounded by $M$). "
            r"Full cluster-robust VCV of the event-study coefficients.}",
            r"\label{tab:honestdid_deltaSD}",
            r"\small \setlength{\tabcolsep}{6pt}",
            r"\begin{tabular}{lrrl}", r"\toprule",
            r"$M$ & Robust LB & Robust UB & Status \\", r"\midrule",
        ]
        for _, row in sd.iterrows():
            status = "contains 0" if row["lb"] <= 0 <= row["ub"] else "excludes 0"
            lines.append(
                f"$M = {float(row['M']):.3f}$ & {float(row['lb']):.4f} & "
                f"{float(row['ub']):.4f} & {status} \\\\"
            )
        lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
        (TABLES / "table_honestdid_deltaSD.tex").write_text(
            "\n".join(lines), encoding="utf-8")
        return breakdown
    except Exception as exc:  # noqa: BLE001
        print(f"[P5] Delta-SD failed: {type(exc).__name__}: {exc}")
        return None


# =================== P6+P7: score sensitivity + voting normalisation ===
USECOLS = ["tag", "week_start", "question_id", "owner_user_id",
           "title", "body_length", "has_code",
           "score", "answer_count", "has_accepted_answer", "is_closed"]


def load_raw_all():
    t0 = time.perf_counter()
    files = sorted(RAW_SO.glob("stackoverflow_question_type_raw_*.csv"))
    print(f"[load_raw] reading {len(files)} files")
    frames = []
    for i, f in enumerate(files, start=1):
        frames.append(pd.read_csv(f, usecols=USECOLS))
        if i % 100 == 0:
            print(f"  ... {i}/{len(files)}")
    raw = pd.concat(frames, ignore_index=True)
    raw["tag"] = raw["tag"].replace(TAG_ALIASES)
    raw = raw.drop_duplicates(["question_id", "tag"]).reset_index(drop=True)
    raw["week_start"] = pd.to_datetime(raw["week_start"], errors="coerce")
    for c in ["question_id", "body_length", "has_code", "score",
              "answer_count", "has_accepted_answer", "is_closed"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    print(f"[load_raw] {len(raw):,} rows; elapsed {time.perf_counter()-t0:.0f}s")
    return raw


def build_threshold_panel(raw: pd.DataFrame, voting_normalise: bool = False
                          ) -> pd.DataFrame:
    df = classify_questions(raw)
    acc = (df["has_accepted_answer"].fillna(0) == 1)
    closed = (df["is_closed"].fillna(0) == 1)
    base_curated = acc & ~closed

    score = df["score"].fillna(0).astype(float)

    if voting_normalise:
        # Voting-baseline normalisation: rescale post-period score by
        # ratio of pre to post mean(|score|) per tag-week.  Simplest
        # implementation: rescale by ratio of mean(|score|) pre and post
        # at the *tag* level.
        df_tmp = df.assign(abs_score=score.abs(),
                           is_post=(df["week_start"] >= CHATGPT_RELEASE))
        tag_means = (df_tmp.groupby(["tag", "is_post"])["abs_score"]
                     .mean().unstack(fill_value=np.nan))
        # pre = column False, post = column True
        if True in tag_means.columns and False in tag_means.columns:
            ratio = tag_means[False] / tag_means[True].replace(0, np.nan)
            # Clip ratio to a reasonable range
            ratio = ratio.replace([np.inf, -np.inf], np.nan).fillna(1.0)
            ratio = ratio.clip(0.5, 3.0)
            df_tmp = df_tmp.merge(ratio.rename("vote_ratio").reset_index(),
                                  on="tag", how="left")
            scale = np.where(df_tmp["is_post"], df_tmp["vote_ratio"], 1.0)
            score = score * scale
            print(f"  [voting_norm] applied scaling; "
                  f"mean ratio={ratio.mean():.3f}, "
                  f"median={ratio.median():.3f}")

    # Build flags for each threshold
    flags = {}
    for k in [0, 1, 2, 3, 4, 5]:
        flags[f"hv_score_ge_{k}"] = (
            base_curated & (score >= k)).astype("int8")
    for col, f in flags.items():
        df[col] = f
    panel = (df.groupby(["tag", "week_start", "question_type",
                         "substitutable_type"], dropna=False)
             .agg(**{c: (c, "sum") for c in flags.keys()},
                  questions_count=("question_id", "nunique"))
             .reset_index())
    panel = panel.sort_values(["tag", "week_start", "question_type"]
                              ).reset_index(drop=True)
    panel["week_start"] = pd.to_datetime(panel["week_start"])
    panel = panel[panel["week_start"] >= PANEL_WEEK_MIN].reset_index(drop=True)
    # Merge AI
    ai = pd.read_csv(AI_REAL)[["tag", AI_VAR]]
    panel = panel.merge(ai, on="tag", how="left", validate="m:1")
    panel["post"] = (panel["week_start"] >= CHATGPT_RELEASE).astype(int)
    return panel


def fit_ddd_outcome(panel: pd.DataFrame, outcome: str):
    work = panel.copy()
    work["tag_qtype"] = (work["tag"].astype(str)
                        + "::" + work["question_type"].astype(str))
    work["week_id"] = work["week_start"].dt.strftime("%Y-%m-%d")
    work["ai"] = work[AI_VAR].astype(float)
    work["sub"] = work["substitutable_type"].astype(int)
    work["ai_post"] = work["ai"] * work["post"]
    work["ai_sub"] = work["ai"] * work["sub"]
    work["post_sub"] = work["post"] * work["sub"]
    work["ai_post_sub"] = work["ai"] * work["post"] * work["sub"]
    work["log_y"] = np.log1p(work[outcome])
    fml = ("log_y ~ ai_post + ai_sub + post_sub + ai_post_sub "
           "| tag_qtype + week_id")
    return pf.feols(fml, data=work, vcov={"CRV1": "tag"})


def extract_triple(m):
    key = "ai_post_sub"
    coefs = m.coef(); ses = m.se(); pvals = m.pvalue(); ci = m.confint()
    lcol = "2.5%" if "2.5%" in ci.columns else "2.5 %"
    hcol = "97.5%" if "97.5%" in ci.columns else "97.5 %"
    return {
        "beta": float(coefs[key]), "se": float(ses[key]),
        "p": float(pvals[key]),
        "ci_low": float(ci.loc[key, lcol]),
        "ci_high": float(ci.loc[key, hcol]),
        "n": int(m._N),
    }


def run_p6_score_sensitivity(raw: pd.DataFrame):
    print("\n" + "="*60)
    print("[P6] Score threshold sensitivity")
    print("="*60)
    panel = build_threshold_panel(raw, voting_normalise=False)
    rows = []
    for k in [0, 1, 2, 3, 4, 5]:
        out = f"hv_score_ge_{k}"
        m = fit_ddd_outcome(panel, out)
        est = extract_triple(m)
        rows.append({"threshold": f"score $\\geq$ {k}",
                     "k": k,
                     **est,
                     "n_total": int(panel[out].sum())})
        print(f"  k={k}: beta={est['beta']:.4f} SE={est['se']:.4f} "
              f"p={est['p']:.4f} n_artefacts={int(panel[out].sum()):,}")
    out = pd.DataFrame(rows)
    out.to_csv(MODELS / "score_threshold_sensitivity.csv", index=False)
    # LaTeX
    lines = [
        r"\begin{table}[ht]", r"\centering",
        r"\caption{Score-threshold sensitivity of the high-value "
        r"funnel-qualified-post DDD. Each row re-fits the baseline triple "
        r"difference with the dependent variable being the count of "
        r"accepted, non-closed posts whose net score "
        r"meets the threshold. The trajectory of the coefficient as "
        r"$k$ grows is the relevant object: a flat trajectory indicates "
        r"that the displacement is proportional across the value "
        r"distribution; an attenuating trajectory indicates that the "
        r"effect concentrates on lower-value artefacts.}",
        r"\label{tab:score_threshold_sensitivity}",
        r"\small",
        r"\begin{tabular}{lrrrrrr}", r"\toprule",
        r"Threshold & $\hat\beta_{DDD}$ & SE & $p$ & 95\% CI & N obs & "
        r"$N$ artefacts \\", r"\midrule",
    ]
    for _, r in out.iterrows():
        ci = f"[{r['ci_low']:.3f}, {r['ci_high']:.3f}]"
        lines.append(
            f"{r['threshold']} & {r['beta']:.4f} & {r['se']:.4f} & "
            f"{r['p']:.4f} & {ci} & {r['n']:,} & "
            f"{int(r['n_total']):,} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    (TABLES / "table_score_threshold_sensitivity.tex").write_text(
        "\n".join(lines), encoding="utf-8")
    return out


def run_p7_voting_normalised(raw: pd.DataFrame):
    print("\n" + "="*60)
    print("[P7] Voting-baseline-normalised high-value")
    print("="*60)
    panel_norm = build_threshold_panel(raw, voting_normalise=True)
    rows = []
    for k in [1, 2, 5]:
        out = f"hv_score_ge_{k}"
        m = fit_ddd_outcome(panel_norm, out)
        est = extract_triple(m)
        rows.append({"threshold": f"score $\\geq$ {k} (voting-normalised)",
                     "k": k, **est,
                     "n_total": int(panel_norm[out].sum())})
        print(f"  k={k} (norm): beta={est['beta']:.4f} SE={est['se']:.4f} "
              f"p={est['p']:.4f}")
    out = pd.DataFrame(rows)
    out.to_csv(MODELS / "voting_normalised_highvalue.csv", index=False)
    # LaTeX
    lines = [
        r"\begin{table}[ht]", r"\centering",
        r"\caption{Voting-baseline-normalised high-value curated "
        r"artefact DDD. The post-period score is rescaled by the "
        r"ratio of pre-period to post-period mean absolute score at "
        r"the tag level, addressing the concern that post-ChatGPT "
        r"voting volume falls and mechanically depresses scores. "
        r"Rescaling factors are clipped to [0.5, 3.0] to avoid "
        r"extrapolation in low-traffic tags.}",
        r"\label{tab:voting_normalised_highvalue}",
        r"\small",
        r"\begin{tabular}{lrrrrr}", r"\toprule",
        r"Threshold & $\hat\beta_{DDD}$ & SE & $p$ & 95\% CI & "
        r"$N$ artefacts \\", r"\midrule",
    ]
    for _, r in out.iterrows():
        ci = f"[{r['ci_low']:.3f}, {r['ci_high']:.3f}]"
        lines.append(
            f"{r['threshold']} & {r['beta']:.4f} & {r['se']:.4f} & "
            f"{r['p']:.4f} & {ci} & {int(r['n_total']):,} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    (TABLES / "table_voting_normalised_highvalue.tex").write_text(
        "\n".join(lines), encoding="utf-8")
    return out


def main():
    print(f"[main] start {datetime.now().isoformat(timespec='seconds')}")
    # P5: HonestDiD SD bounds
    breakdown_sd = run_p5_honestdid_sd()
    # P6 + P7: load raw once, run both
    raw = load_raw_all()
    p6 = run_p6_score_sensitivity(raw)
    p7 = run_p7_voting_normalised(raw)
    print("\n[main] all three exercises complete")
    print(f"[main] done {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
