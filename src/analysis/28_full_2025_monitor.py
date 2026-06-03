"""Full 100-tag monitor validation on the complete 2025 data (replaces
the 30-tag subset in scripts 21/26): out-of-sample persistence of the
value-disproportionality and the intensive-margin regret of ignoring the
value calibration.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

THIS = Path(__file__).resolve(); ROOT = THIS.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.paths import PROCESSED_DIR, OUTPUTS_DIR  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

CHATGPT = pd.Timestamp("2022-11-30")
VW = PROCESSED_DIR / "value_weighted_funnel_panel.csv"
CLEAN25 = PROCESSED_DIR / "stockoverflow_2025_clean_question_tag.csv"  # fixed below
MODELS = OUTPUTS_DIR / "models"; TABLES = OUTPUTS_DIR / "tables"
RNG = np.random.default_rng(20260602)


def load_clean25():
    p = PROCESSED_DIR / "stackoverflow_2025_clean_question_tag.csv"
    d = pd.read_csv(p, usecols=["question_id", "tag", "creation_date",
                                "score", "has_accepted_answer", "is_closed"])
    d["creation_date"] = pd.to_datetime(d["creation_date"], errors="coerce")
    d = d[d["creation_date"].dt.year == 2025]
    for c in ["score", "has_accepted_answer", "is_closed"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.drop_duplicates(["question_id", "tag"])
    acc = d["has_accepted_answer"].fillna(0) == 1
    clo = d["is_closed"].fillna(0) == 1
    d["hv"] = (acc & ~clo & (d["score"].fillna(0) >= 1)).astype(int)
    nwk = d["creation_date"].dt.isocalendar().week.nunique()
    g = d.groupby("tag").agg(q=("question_id", "nunique"), hv=("hv", "sum"))
    g["q_wk"] = g["q"]/nwk; g["hv_wk"] = g["hv"]/nwk
    return g


def build():
    vw = pd.read_csv(VW); vw["week_start"] = pd.to_datetime(vw["week_start"])
    vw["yr"] = vw["week_start"].dt.year
    pre = vw[vw["week_start"] < CHATGPT].groupby("tag").agg(
        q=("questions_count", "sum"), hv=("high_value_artifacts", "sum"),
        nw=("week_start", "nunique"))
    y24 = vw[vw["yr"] == 2024].groupby("tag").agg(
        q=("questions_count", "sum"), hv=("high_value_artifacts", "sum"),
        nw=("week_start", "nunique"))
    g25 = load_clean25()
    rows = []
    for t in pre.index:
        if t not in y24.index or t not in g25.index:
            continue
        pre_hv = pre.loc[t, "hv"]/pre.loc[t, "nw"]; pre_q = pre.loc[t, "q"]/pre.loc[t, "nw"]
        if pre_hv <= 0 or pre_q <= 0:
            continue
        y24_hv = y24.loc[t, "hv"]/y24.loc[t, "nw"]; y24_q = y24.loc[t, "q"]/y24.loc[t, "nw"]
        a24 = 1 - y24_q/pre_q
        rows.append(dict(
            tag=t, cost=y24_q, naive=max(pre_q-y24_q, 0),
            calibrated=max(pre_hv-y24_hv, 0),
            value=max(pre_hv-g25.loc[t, "hv_wk"], 0),
            hv_drop24=1-y24_hv/pre_hv,
            hv_drop25=1-g25.loc[t, "hv_wk"]/pre_hv,
            a24=a24))
    return pd.DataFrame(rows)


def frac(df, key, b):
    d = df.copy(); d["eff"] = d[key]/d["cost"]
    d = d.sort_values("eff", ascending=False).reset_index(drop=True)
    B = b*d["cost"].sum(); spent = val = 0.0
    for _, r in d.iterrows():
        if spent+r["cost"] <= B:
            spent += r["cost"]; val += r["value"]
        else:
            val += max(B-spent, 0)/r["cost"]*r["value"]; break
    return val/df["value"].sum()


def main():
    df = build()
    print(f"[full monitor] {len(df)} tags", flush=True)
    # persistence
    dd = df[(df["a24"] > 0.05)]
    rho, p = spearmanr(dd["hv_drop24"], dd["hv_drop25"])
    print(f"  persistence Spearman(hv_drop 2024, 2025) = {rho:.3f} (p={p:.4f}, n={len(dd)})", flush=True)
    # VOI / regret
    rows = []
    for b in [0.10, 0.25, 0.40, 0.50]:
        orc = frac(df, "value", b); cal = frac(df, "calibrated", b); nai = frac(df, "naive", b)
        rs = []
        for _ in range(1500):
            d = df.sample(frac=1.0, random_state=RNG.integers(1e9)).reset_index(drop=True)
            d["cc"] = d["cost"].cumsum()/df["cost"].sum()
            rs.append(d[d["cc"] <= b]["value"].sum()/df["value"].sum())
        rows.append(dict(budget=b, oracle=orc, calibrated=cal, naive=nai,
                         random=float(np.mean(rs)),
                         regret_calibrated=(orc-cal)/orc if orc > 0 else np.nan,
                         regret_naive=(orc-nai)/orc if orc > 0 else np.nan))
    out = pd.DataFrame(rows)
    out.to_csv(MODELS / "full_2025_voi_regret.csv", index=False)
    print(out.to_string(index=False), flush=True)
    pd.DataFrame([{"persistence_rho": rho, "persistence_p": p, "n": len(dd)}]
                 ).to_csv(MODELS / "full_2025_persistence.csv", index=False)

    # rewrite the two paper tables with full-100-tag numbers
    lines = [r"\begin{table}[ht]", r"\centering",
        r"\caption{Intensive-margin value of calibration, \textbf{full "
        r"100-tag 2025 panel} (out of sample). A manager allocates an "
        r"intervention budget $B$ (a fraction of total tag activity) to "
        r"protect realised 2025 high-value flow, ranking by efficiency. "
        r"\textbf{Oracle} is the perfect-foresight cost-constrained "
        r"optimum; \textbf{Calibrated} ranks by end-2024 "
        r"high-value-at-risk; \textbf{Naive} by raw activity loss; "
        r"\textbf{Random} averages shuffles. Cells are the share of "
        r"realised 2025 high-value loss captured; the regret of a rule is "
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
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
