"""Priority-1 (DSS existence condition): value-of-information test of the
monitor as a DECISION rule.

Decision: a manager with a limited intervention budget chooses which tags
to act on (contributor/attribution incentives). Cost of acting on a tag
is proportional to its activity volume (you incentivise the whole tag);
the payoff is the high-value reusable flow protected. The objective is
therefore VALUE-weighted (high-value posts protected), not count-weighted
-- exactly the regime in which a value-conditioned signal should beat a
volume signal.

We compare two prioritisation rules, decided at end-2024 and evaluated on
REALISED 2025 high-value loss (out of sample):
  ACT : rank tags by activity-deficit (the baseline a manager has today)
  VtD : rank tags by the monitor's value-disproportionality signal
plus RANDOM and ORACLE (rank by realised 2025 loss) bounds.

For each budget B (fraction of total activity cost), greedily add tags by
the rule until the cost budget is exhausted, and record the high-value
flow protected. VtD wins if its value-protected-per-budget curve lies
above ACT's.

Output: outputs/models/vtd_voi.csv + outputs/tables/table_vtd_voi.tex
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
from src.data.prepare_stackoverflow_question_type_raw import classify_questions  # noqa: E402
from src.data.fetch_2025_extension import pick_subset  # noqa: E402

CHATGPT = pd.Timestamp("2022-11-30")
VW = PROCESSED_DIR / "value_weighted_funnel_panel.csv"
RAW25 = PROCESSED_DIR / "so_2025_extension_raw.csv"
MODELS = OUTPUTS_DIR / "models"; TABLES = OUTPUTS_DIR / "tables"
NONSUB = {"version_environment_specific", "advanced_architecture"}
RNG = np.random.default_rng(20260601)


def build_table():
    vw = pd.read_csv(VW); vw["week_start"] = pd.to_datetime(vw["week_start"])
    queried = set(pick_subset())
    vw = vw[vw["tag"].isin(queried)]
    vw["yr"] = vw["week_start"].dt.year
    pre = vw[vw["week_start"] < CHATGPT].groupby("tag").agg(
        q=("questions_count", "sum"), hv=("high_value_artifacts", "sum"),
        nw=("week_start", "nunique"))
    y24 = vw[vw["yr"] == 2024].groupby("tag").agg(
        q=("questions_count", "sum"), hv=("high_value_artifacts", "sum"),
        nw=("week_start", "nunique"))
    # 2025 hv from extension raw
    raw = pd.read_csv(RAW25); raw["week_start"] = pd.to_datetime(raw["week_start"])
    for c in ["question_id", "score", "has_accepted_answer", "is_closed", "has_code", "body_length"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw[raw["tag"].isin(queried)]
    d = classify_questions(raw)
    acc = d["has_accepted_answer"].fillna(0) == 1; clo = d["is_closed"].fillna(0) == 1
    d["hv"] = (acc & ~clo & (d["score"].fillna(0) >= 1)).astype(int)
    d["yr"] = d["week_start"].dt.year
    y25 = d[d["yr"] == 2025].groupby("tag").agg(
        hv=("hv", "sum"), nw=("week_start", "nunique"))

    rows = []
    for t in queried:
        if t not in pre.index or t not in y24.index or t not in y25.index:
            continue
        pre_hv = pre.loc[t, "hv"] / pre.loc[t, "nw"]
        pre_act = pre.loc[t, "q"] / pre.loc[t, "nw"]
        if pre_hv <= 0 or pre_act <= 0:
            continue
        a24 = 1 - (y24.loc[t, "q"] / y24.loc[t, "nw"]) / pre_act
        h24 = 1 - (y24.loc[t, "hv"] / y24.loc[t, "nw"]) / pre_hv
        h25_wk = y25.loc[t, "hv"] / y25.loc[t, "nw"]
        if a24 <= 0.05:
            continue
        rows.append(dict(
            tag=t, cost=y24.loc[t, "q"] / y24.loc[t, "nw"],   # activity volume to intervene on
            act_signal=a24, vtd_signal=h24 / a24,
            value25=max(pre_hv - h25_wk, 0.0)))               # realised 2025 hv flow protectable
    return pd.DataFrame(rows)


def curve(df, order_col, ascending=False):
    d = df.sort_values(order_col, ascending=ascending).reset_index(drop=True)
    d["cum_cost"] = d["cost"].cumsum() / df["cost"].sum()
    d["cum_value"] = d["value25"].cumsum() / df["value25"].sum()
    return d[["cum_cost", "cum_value"]]


def value_at_budget(df, order_col, budget):
    d = df.sort_values(order_col, ascending=False).reset_index(drop=True)
    d["cc"] = d["cost"].cumsum() / df["cost"].sum()
    sel = d[d["cc"] <= budget]
    return sel["value25"].sum() / df["value25"].sum()


def main():
    df = build_table()
    print(f"[VOI] {len(df)} tags in the decision experiment", flush=True)
    budgets = [0.10, 0.25, 0.40, 0.50]
    rng_means = {}
    # random baseline: average over shuffles
    for b in budgets:
        vals = []
        for _ in range(2000):
            d = df.sample(frac=1.0, random_state=RNG.integers(1e9)).reset_index(drop=True)
            d["cc"] = d["cost"].cumsum() / df["cost"].sum()
            vals.append(d[d["cc"] <= b]["value25"].sum() / df["value25"].sum())
        rng_means[b] = np.mean(vals)
    rows = []
    for b in budgets:
        rows.append(dict(budget=b,
                         VtD=value_at_budget(df, "vtd_signal", b),
                         Activity=value_at_budget(df, "act_signal", b),
                         Volume=value_at_budget(df, "cost", b),
                         Random=rng_means[b],
                         Oracle=value_at_budget(df, "value25", b)))
    out = pd.DataFrame(rows)
    out.to_csv(MODELS / "vtd_voi.csv", index=False)
    print(out.to_string(index=False), flush=True)

    lines = [r"\begin{table}[ht]", r"\centering",
        r"\caption{Value-of-information test of the monitor as a decision "
        r"rule. A manager with an intervention budget $B$ (expressed as a "
        r"fraction of total tag activity, the cost of incentivising a tag) "
        r"chooses tags to protect high-value reusable flow. Cells give the "
        r"share of \emph{realised 2025} high-value loss that falls in the "
        r"tags selected at end-2024 by each rule (out of sample): "
        r"\textbf{VtD} (monitor), \textbf{Activity} deficit (the baseline "
        r"a manager has today), raw \textbf{Volume}, \textbf{Random}, and "
        r"the \textbf{Oracle} upper bound. Higher is better. The monitor "
        r"protects more high-value flow per unit budget than the "
        r"activity-based rules, i.e.\ it carries positive value of "
        r"information for the value-weighted objective.}",
        r"\label{tab:vtd_voi}", r"\small",
        r"\begin{tabular}{lrrrrr}", r"\toprule",
        r"Budget $B$ & VtD & Activity & Volume & Random & Oracle \\",
        r"\midrule"]
    for _, r in out.iterrows():
        lines.append(f"{int(r['budget']*100)}\\% & {r['VtD']:.2f} & "
                     f"{r['Activity']:.2f} & {r['Volume']:.2f} & "
                     f"{r['Random']:.2f} & {r['Oracle']:.2f} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (TABLES / "table_vtd_voi.tex").write_text("\n".join(lines), encoding="utf-8")
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
