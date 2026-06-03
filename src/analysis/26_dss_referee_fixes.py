"""Current-data fixes for the DSS referee:
  #2  correct the VOI table -- the oracle must be the true cost-constrained
      (fractional-knapsack) optimum, which no feasible rule can beat.
  B(iii) intensive-margin regret -- does allocating effort by the
      value-CALIBRATED signal (high-value-at-risk) beat allocating by raw
      activity, out of sample (2024 signal -> realised 2025 high-value
      loss)? Quantify the regret of ignoring calibration.
  #3  a single pre-specified SHAPE test -- one model with the triple
      difference interacted with the (centred) net-score level, testing
      the average effect across the value distribution and its slope,
      instead of 'four bins individually significant'.

Outputs: outputs/models/dss_fixes_*.csv, outputs/tables/table_vtd_voi.tex
(overwrites the buggy one), outputs/tables/table_shape_test.tex
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pyfixest as pf

THIS = Path(__file__).resolve(); ROOT = THIS.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.paths import PROCESSED_DIR, OUTPUTS_DIR  # noqa: E402
from src.data.prepare_stackoverflow_question_type_raw import classify_questions  # noqa: E402
from src.data.fetch_2025_extension import pick_subset  # noqa: E402

CHATGPT = pd.Timestamp("2022-11-30")
VW = PROCESSED_DIR / "value_weighted_funnel_panel.csv"
RAW25 = PROCESSED_DIR / "so_2025_extension_raw.csv"
BIN = PROCESSED_DIR / "score_bin_artefact_panel.csv"
MODELS = OUTPUTS_DIR / "models"; TABLES = OUTPUTS_DIR / "tables"
AI = "ai_answerability_structural"
RNG = np.random.default_rng(20260601)


# ---------- per-tag decision table (2024 signals -> 2025 realised) ----------
def decision_table():
    vw = pd.read_csv(VW); vw["week_start"] = pd.to_datetime(vw["week_start"])
    queried = set(pick_subset()); vw = vw[vw["tag"].isin(queried)]
    vw["yr"] = vw["week_start"].dt.year
    pre = vw[vw["week_start"] < CHATGPT].groupby("tag").agg(
        q=("questions_count", "sum"), hv=("high_value_artifacts", "sum"),
        nw=("week_start", "nunique"))
    y24 = vw[vw["yr"] == 2024].groupby("tag").agg(
        q=("questions_count", "sum"), hv=("high_value_artifacts", "sum"),
        nw=("week_start", "nunique"))
    raw = pd.read_csv(RAW25); raw["week_start"] = pd.to_datetime(raw["week_start"])
    for c in ["question_id", "score", "has_accepted_answer", "is_closed",
              "has_code", "body_length"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw[raw["tag"].isin(queried)]
    d = classify_questions(raw)
    acc = d["has_accepted_answer"].fillna(0) == 1; clo = d["is_closed"].fillna(0) == 1
    d["hv"] = (acc & ~clo & (d["score"].fillna(0) >= 1)).astype(int)
    d["yr"] = d["week_start"].dt.year
    y25 = d[d["yr"] == 2025].groupby("tag").agg(hv=("hv", "sum"),
                                                nw=("week_start", "nunique"))
    rows = []
    for t in queried:
        if t not in pre.index or t not in y24.index or t not in y25.index:
            continue
        pre_hv = pre.loc[t, "hv"]/pre.loc[t, "nw"]; pre_q = pre.loc[t, "q"]/pre.loc[t, "nw"]
        if pre_hv <= 0 or pre_q <= 0:
            continue
        y24_hv = y24.loc[t, "hv"]/y24.loc[t, "nw"]; y24_q = y24.loc[t, "q"]/y24.loc[t, "nw"]
        y25_hv = y25.loc[t, "hv"]/y25.loc[t, "nw"]
        rows.append(dict(
            tag=t,
            cost=y24_q,                                  # effort scale = activity volume
            naive=max(pre_q - y24_q, 0),                 # 2024 activity-loss signal
            calibrated=max(pre_hv - y24_hv, 0),          # 2024 high-value-at-risk (calibrated)
            value=max(pre_hv - y25_hv, 0)))              # realised 2025 high-value loss
    return pd.DataFrame(rows)


def frac_knapsack_value(df, key, budget_frac):
    """Value captured by a fractional-knapsack fill ordered by `key` per
    unit cost, under a cost budget = budget_frac * total cost."""
    d = df.copy()
    d["eff"] = d[key] / d["cost"]
    d = d.sort_values("eff", ascending=False).reset_index(drop=True)
    B = budget_frac * d["cost"].sum()
    spent = 0.0; val = 0.0
    for _, r in d.iterrows():
        if spent + r["cost"] <= B:
            spent += r["cost"]; val += r["value"]
        else:
            frac = max(B - spent, 0) / r["cost"]
            val += frac * r["value"]; break
    return val / df["value"].sum()


def voi_and_regret():
    df = decision_table()
    print(f"[VOI/regret] {len(df)} tags", flush=True)
    budgets = [0.10, 0.25, 0.40, 0.50]
    rows = []
    for b in budgets:
        oracle = frac_knapsack_value(df, "value", b)        # true upper bound (perfect foresight)
        calib = frac_knapsack_value(df, "calibrated", b)    # rank by 2024 HV-at-risk / cost
        naive = frac_knapsack_value(df, "naive", b)         # rank by 2024 activity-loss / cost
        # random
        rs = []
        for _ in range(2000):
            d = df.sample(frac=1.0, random_state=RNG.integers(1e9)).reset_index(drop=True)
            d["cc"] = d["cost"].cumsum() / df["cost"].sum()
            rs.append(d[d["cc"] <= b]["value"].sum() / df["value"].sum())
        rnd = float(np.mean(rs))
        rows.append(dict(budget=b, oracle=oracle, calibrated=calib,
                         naive=naive, random=rnd,
                         regret_naive=(oracle-naive)/oracle if oracle>0 else np.nan,
                         regret_calibrated=(oracle-calib)/oracle if oracle>0 else np.nan))
    out = pd.DataFrame(rows); out.to_csv(MODELS / "dss_fixes_voi_regret.csv", index=False)
    print(out.to_string(index=False), flush=True)
    # sanity: oracle must dominate
    bad = out[(out["oracle"] < out["calibrated"]-1e-9) | (out["oracle"] < out["naive"]-1e-9)]
    print(f"[check] rows where oracle < a feasible rule (should be 0): {len(bad)}", flush=True)

    lines = [r"\begin{table}[ht]", r"\centering",
        r"\caption{Intensive-margin value of calibration (out of sample). "
        r"A manager allocates an intervention budget $B$ (a fraction of "
        r"total tag activity) across tags to protect realised 2025 "
        r"high-value flow, ranking by efficiency (value per unit effort). "
        r"\textbf{Oracle} uses perfect foresight (the true cost-constrained "
        r"optimum, an upper bound); \textbf{Calibrated} ranks by the "
        r"end-2024 high-value-at-risk the system computes; \textbf{Naive} "
        r"ranks by the raw activity-loss signal; \textbf{Random} averages "
        r"shuffles. Cells are the share of realised 2025 high-value loss "
        r"captured. The regret of ignoring calibration is "
        r"$(\text{Oracle}-\text{rule})/\text{Oracle}$.}",
        r"\label{tab:vtd_voi}", r"\small",
        r"\begin{tabular}{lrrrrrr}", r"\toprule",
        r"$B$ & Oracle & Calibrated & Naive & Random & "
        r"Regret$_{\text{calib}}$ & Regret$_{\text{naive}}$ \\", r"\midrule"]
    for _, r in out.iterrows():
        lines.append(f"{int(r['budget']*100)}\\% & {r['oracle']:.2f} & "
                     f"{r['calibrated']:.2f} & {r['naive']:.2f} & {r['random']:.2f} & "
                     f"{r['regret_calibrated']:.2f} & {r['regret_naive']:.2f} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (TABLES / "table_vtd_voi.tex").write_text("\n".join(lines), encoding="utf-8")
    return out


# ---------- #3 pre-specified shape test ----------
def shape_test():
    p = pd.read_csv(BIN); p["week_start"] = pd.to_datetime(p["week_start"])
    bincols = {"score_eq_0": 0, "score_eq_1": 1, "score_eq_2": 2,
               "score_eq_3": 3, "score_eq_4": 4, "score_ge_5": 5}
    long = p.melt(id_vars=["tag", "week_start", "question_type",
                           "substitutable_type", AI, "post_chatgpt"],
                  value_vars=list(bincols), var_name="binname", value_name="cnt")
    long["level"] = long["binname"].map(bincols).astype(float)
    long["lvl_c"] = long["level"] - long["level"].mean()   # centred
    long["ai"] = long[AI].astype(float); long["sub"] = long["substitutable_type"].astype(int)
    long["post"] = long["post_chatgpt"].astype(int)
    long["aps"] = long["ai"]*long["post"]*long["sub"]
    long["ai_post"] = long["ai"]*long["post"]; long["ai_sub"] = long["ai"]*long["sub"]
    long["post_sub"] = long["post"]*long["sub"]
    long["aps_lvl"] = long["aps"]*long["lvl_c"]
    long["log_y"] = np.log1p(long["cnt"])
    long["tag_qtype"] = long["tag"].astype(str)+"::"+long["question_type"].astype(str)
    long["wk_lvl"] = long["week_start"].dt.strftime("%Y-%m-%d")+"_"+long["level"].astype(int).astype(str)
    m = pf.feols("log_y ~ aps + aps_lvl + ai_post + ai_sub + post_sub "
                 "| tag_qtype + wk_lvl", data=long, vcov={"CRV1": "tag"})
    co, se, pv = m.coef(), m.se(), m.pvalue()
    res = {"avg_effect": float(co["aps"]), "avg_p": float(pv["aps"]),
           "slope": float(co["aps_lvl"]), "slope_p": float(pv["aps_lvl"]), "n": int(m._N)}
    print(f"[shape] avg effect across value distribution = {res['avg_effect']:.4f} "
          f"(p={res['avg_p']:.4f}); slope over score = {res['slope']:.4f} "
          f"(p={res['slope_p']:.4f})", flush=True)
    pd.DataFrame([res]).to_csv(MODELS / "dss_fixes_shape.csv", index=False)
    lines = [r"\begin{table}[ht]", r"\centering",
        r"\caption{Pre-specified shape test of the value gradient. A single "
        r"model stacks the six mutually exclusive net-score bins and fits "
        r"the triple difference plus its interaction with the (centred) "
        r"net-score level, clustered by tag. The \emph{average} coefficient "
        r"tests whether the displacement is present across the value "
        r"distribution (the focal C1 hypothesis); the \emph{slope} tests "
        r"how it varies with score. This replaces multiple per-bin tests "
        r"with one declared statistic.}",
        r"\label{tab:shape_test}", r"\small",
        r"\begin{tabular}{lrr}", r"\toprule",
        r"Quantity & Estimate & $p$ \\", r"\midrule",
        f"Average displacement across bins & {res['avg_effect']:.3f} & {res['avg_p']:.3f} \\\\",
        f"Slope over net-score level & {res['slope']:.3f} & {res['slope_p']:.3f} \\\\",
        r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (TABLES / "table_shape_test.tex").write_text("\n".join(lines), encoding="utf-8")
    return res


if __name__ == "__main__":
    voi_and_regret()
    shape_test()
    print("[done]", flush=True)
