"""Recompute budget-constrained VOI/regret with the full 2025 panel."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.paths import FIGURES_DIR, PROCESSED_DIR, TABLES_DIR  # noqa: E402

CHATGPT = pd.Timestamp("2022-11-30")
RNG = np.random.default_rng(20260602)


def build_decision_table(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.copy()
    p["week_start"] = pd.to_datetime(p["week_start"])
    p["year"] = p["week_start"].dt.year
    p["accepted_answers"] = pd.to_numeric(p.get("accepted_answers", 0), errors="coerce").fillna(0)
    p["closed_questions"] = pd.to_numeric(p.get("closed_questions", 0), errors="coerce").fillna(0)
    p["questions"] = pd.to_numeric(p["questions"], errors="coerce").fillna(0)
    p["high_value_proxy"] = np.maximum(p["accepted_answers"] - p["closed_questions"], 0)
    pre = p[p["week_start"] < CHATGPT].groupby("tag").agg(pre_q=("questions", "sum"), pre_hv=("high_value_proxy", "sum"), pre_weeks=("week_start", "nunique"))
    y24 = p[p["year"] == 2024].groupby("tag").agg(q24=("questions", "sum"), hv24=("high_value_proxy", "sum"), weeks24=("week_start", "nunique"))
    y25 = p[p["year"] == 2025].groupby("tag").agg(q25=("questions", "sum"), hv25=("high_value_proxy", "sum"), weeks25=("week_start", "nunique"))
    rows = []
    for tag in sorted(set(pre.index) & set(y24.index) & set(y25.index)):
        if pre.loc[tag, "pre_weeks"] <= 0 or y24.loc[tag, "weeks24"] <= 0 or y25.loc[tag, "weeks25"] <= 0:
            continue
        pre_q_w = pre.loc[tag, "pre_q"] / pre.loc[tag, "pre_weeks"]
        pre_hv_w = pre.loc[tag, "pre_hv"] / pre.loc[tag, "pre_weeks"]
        q24_w = y24.loc[tag, "q24"] / y24.loc[tag, "weeks24"]
        hv24_w = y24.loc[tag, "hv24"] / y24.loc[tag, "weeks24"]
        hv25_w = y25.loc[tag, "hv25"] / y25.loc[tag, "weeks25"]
        if pre_q_w <= 0:
            continue
        activity_decline = max(1 - q24_w / pre_q_w, 0)
        hv_decline_24 = max(1 - hv24_w / pre_hv_w, 0) if pre_hv_w > 0 else 0
        value25_loss = max(pre_hv_w - hv25_w, 0)
        rows.append({
            "tag": tag,
            "cost": max(q24_w, 1e-9),
            "activity_signal": activity_decline,
            "calibrated_signal": activity_decline * (hv_decline_24 / activity_decline if activity_decline > 0 else 0),
            "value_weighted_signal": hv_decline_24,
            "value25_loss": value25_loss,
        })
    return pd.DataFrame(rows)


def value_for_order(df: pd.DataFrame, order: list[str], budget: float) -> float:
    total_cost = df["cost"].sum()
    cap = budget * total_cost
    spent = 0.0
    value = 0.0
    indexed = df.set_index("tag")
    for tag in order:
        cost = float(indexed.loc[tag, "cost"])
        if spent + cost <= cap + 1e-12:
            spent += cost
            value += float(indexed.loc[tag, "value25_loss"])
    return value


def ranked(df: pd.DataFrame, col: str) -> list[str]:
    return df.sort_values(col, ascending=False)["tag"].tolist()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=PROCESSED_DIR / "panel_tag_week_question_type_2020_2025.csv")
    parser.add_argument("--table", type=Path, default=TABLES_DIR / "voi_regret_2025_full.csv")
    parser.add_argument("--figure", type=Path, default=FIGURES_DIR / "regret_budget_curves_2025_full.pdf")
    args = parser.parse_args()
    panel = pd.read_csv(args.panel)
    df = build_decision_table(panel)
    if df.empty or df["value25_loss"].sum() <= 0:
        raise SystemExit("No positive 2025 high-value loss proxy available; cannot compute VOI/regret.")
    budgets = [0.10, 0.25, 0.50]
    orders = {
        "oracle": ranked(df, "value25_loss"),
        "calibrated": ranked(df, "calibrated_signal"),
        "activity": ranked(df, "activity_signal"),
        "value_weighted": ranked(df, "value_weighted_signal"),
    }
    random_values = {}
    for b in budgets:
        vals = []
        tags = df["tag"].tolist()
        for _ in range(500):
            RNG.shuffle(tags)
            vals.append(value_for_order(df, list(tags), b))
        random_values[b] = float(np.mean(vals))
    rows = []
    for b in budgets:
        oracle = value_for_order(df, orders["oracle"], b)
        calibrated = value_for_order(df, orders["calibrated"], b)
        activity = value_for_order(df, orders["activity"], b)
        value_weighted = value_for_order(df, orders["value_weighted"], b)
        random = random_values[b]
        feasible = [calibrated, activity, value_weighted, random]
        violations = int(any(v > oracle + 1e-9 for v in feasible))
        if violations:
            raise SystemExit(f"Invalid VOI: feasible rule exceeds oracle at budget {b}")
        rows.append({
            "budget": b,
            "oracle_value": oracle,
            "calibrated_value": calibrated,
            "activity_value": activity,
            "value_weighted_detector_value": value_weighted,
            "random_value": random,
            "calibrated_regret": oracle - calibrated,
            "activity_regret": oracle - activity,
            "random_regret": oracle - random,
            "calibrated_regret_pct": (oracle - calibrated) / oracle if oracle else np.nan,
            "activity_regret_pct": (oracle - activity) / oracle if oracle else np.nan,
            "random_regret_pct": (oracle - random) / oracle if oracle else np.nan,
            "oracle_violations": violations,
        })
    out = pd.DataFrame(rows)
    args.table.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.table, index=False)

    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    for col, label in [
        ("calibrated_regret_pct", "Calibrated"),
        ("activity_regret_pct", "Activity"),
        ("random_regret_pct", "Random"),
    ]:
        ax.plot(out["budget"] * 100, out[col] * 100, marker="o", label=label)
    ax.set_xlabel("Budget (% of 2024 activity cost)")
    ax.set_ylabel("Regret relative to oracle (%)")
    ax.set_title("VOI Regret Curves, Full 2025 Panel")
    ax.legend()
    fig.tight_layout()
    args.figure.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.figure)
    plt.close(fig)
    print(out.to_string(index=False))
    print(f"saved {args.table}")
    print(f"saved {args.figure}")


if __name__ == "__main__":
    main()
