"""
Bloque 6 - Validaciones numericas formales de la extension Reusable Funnel.

Verifica:
  (1) Monotonia: reusable <= accepted_nonneg <= accepted <= answered <= questions
      en TODAS las celdas (no muestreo).
  (2) Shares en [0,1].
  (3) 100 tags unicos en el panel.
  (4) 7 question_types unicos.
  (5) Cutoff post_chatgpt corresponde a 2022-11-30.
  (6) DDD baseline (questions_count) ~ -0.108 (tolerancia 0.03).
  (7) Implied displacement (questions_count) ~ 67,000 (tolerancia +/- 10%).

Output: outputs/diagnostics/reusable_extension_validation_report.md
        Si alguna check falla, escribe diagnostico y status=FAIL.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.paths import OUTPUTS_DIR, PROCESSED_DIR  # noqa: E402

PANEL = PROCESSED_DIR / "reusable_artifact_funnel_panel.csv"
RESOLV = PROCESSED_DIR / "resolvability_panel.csv"
DDD_RESULTS = OUTPUTS_DIR / "models" / "reusable_funnel_ddd_results.csv"
DEC = OUTPUTS_DIR / "models" / "decline_decomposition.csv"
REPORT = OUTPUTS_DIR / "diagnostics" / "reusable_extension_validation_report.md"


def fmt_check(name: str, passed: bool, detail: str = "") -> str:
    icon = "[OK]" if passed else "[FAIL]"
    return f"- {icon} **{name}** {('-' + ' ' + detail) if detail else ''}"


def main() -> None:
    print(f"[main] start {datetime.now().isoformat(timespec='seconds')}")
    panel = pd.read_csv(PANEL)
    panel["week_start"] = pd.to_datetime(panel["week_start"])

    checks: list[tuple[str, bool, str]] = []

    # (1) Monotonia
    chain = [
        ("reusable_artifacts", "accepted_nonnegative_questions"),
        ("accepted_nonnegative_questions", "accepted_answer_questions"),
        ("accepted_nonclosed_questions", "accepted_answer_questions"),
        ("accepted_answer_questions", "answered_questions"),
        ("answered_questions", "questions_count"),
    ]
    mon_lines = []
    mon_all_ok = True
    for smaller, larger in chain:
        v = int((panel[smaller] > panel[larger]).sum())
        ok = v == 0
        mon_all_ok = mon_all_ok and ok
        mon_lines.append(
            f"  - {'[OK]' if ok else '[FAIL]'} `{smaller} <= {larger}`: "
            f"{v} violations across {len(panel):,} cells"
        )
    checks.append(("Monotonicity holds across all funnel chains",
                   mon_all_ok, "\n" + "\n".join(mon_lines)))

    # (2) Shares in [0,1]
    resolv = pd.read_csv(RESOLV) if RESOLV.exists() else None
    if resolv is not None:
        share_cols = ["accepted_share", "answered_share",
                      "unanswered_share", "no_accepted_share", "closed_share"]
        bad = {}
        for c in share_cols:
            if c not in resolv.columns:
                continue
            v = resolv[c].dropna()
            below = int((v < -1e-9).sum())
            above = int((v > 1 + 1e-9).sum())
            if below or above:
                bad[c] = (below, above)
        all_ok = len(bad) == 0
        detail = ("all share columns in [0,1] (numeric tolerance 1e-9)"
                  if all_ok else f"violations: {bad}")
        checks.append(("All resolvability shares in [0,1]", all_ok, detail))
    else:
        checks.append(("Resolvability panel available for share check",
                       False, "resolvability_panel.csv not found"))

    # (3) 100 unique tags
    n_tags = int(panel["tag"].nunique())
    ok = n_tags == 100
    checks.append(("100 unique tags in funnel panel", ok, f"n_tags={n_tags}"))

    # (4) 7 question_types
    n_qt = int(panel["question_type"].nunique())
    ok = n_qt == 7
    checks.append(("7 unique question_types", ok, f"n_qt={n_qt}"))

    # (5) Post-cutoff = 2022-11-30 (panel cells)
    cutoff = pd.Timestamp("2022-11-30")
    n_pre_thr = int((panel["week_start"] < cutoff).sum())
    n_post_thr = int((panel["week_start"] >= cutoff).sum())
    n_pre_col = int((panel["post_chatgpt"] == 0).sum())
    n_post_col = int((panel["post_chatgpt"] == 1).sum())
    ok = (n_pre_thr == n_pre_col) and (n_post_thr == n_post_col)
    checks.append((
        "post_chatgpt flag matches threshold 2022-11-30",
        ok,
        f"threshold pre/post={n_pre_thr}/{n_post_thr}, "
        f"flag pre/post={n_pre_col}/{n_post_col}"))

    # (6) DDD baseline for questions_count ~ -0.108
    ddd = pd.read_csv(DDD_RESULTS)
    base = ddd[ddd["outcome"] == "questions_count"].iloc[0]
    beta_ok = abs(base["beta"] - (-0.108)) < 0.03
    checks.append((
        "DDD baseline (questions_count) within 0.03 of -0.108",
        beta_ok,
        f"beta={base['beta']:.4f}, diff={base['beta'] - (-0.108):+.4f}"))

    # (7) Implied displacement (questions_count) within +/-10% of 67,000
    impl = float(base["implied_displaced"])
    dev = abs(impl - 67000) / 67000
    impl_ok = dev <= 0.10
    checks.append((
        "Implied displacement (questions_count) within 10% of 67,000",
        impl_ok,
        f"implied={impl:,.0f}, deviation={dev*100:.1f}%"))

    # (8) Decline decomposition: trend shortfall ~ 1.42M
    if DEC.exists():
        dec = pd.read_csv(DEC)
        row = dec[dec["target"] == "weekly_questions"].iloc[0]
        ts = float(row["trend_shortfall"])
        ts_ok = abs(ts - 1.42e6) / 1.42e6 < 0.05
        checks.append((
            "Trend shortfall (questions) within 5% of 1.42M",
            ts_ok,
            f"trend_shortfall={ts:,.0f}, dev={abs(ts-1.42e6)/1.42e6*100:.2f}%"))
        share = float(row["ddd_share_of_trend_shortfall"])
        share_ok = 0.03 <= share <= 0.08
        checks.append((
            "DDD share of trend shortfall within [3%, 8%] (baseline ~4-5%)",
            share_ok,
            f"share={share*100:.2f}%"))

    # (9) Cero missing values en columnas clave del funnel panel
    keycols = [
        "tag", "week_start", "question_type", "substitutable_type",
        "questions_count", "answered_questions", "accepted_answer_questions",
        "accepted_nonclosed_questions", "accepted_nonnegative_questions",
        "reusable_artifacts", "ai_answerability_structural", "post_chatgpt",
    ]
    miss = {c: int(panel[c].isna().sum()) for c in keycols if c in panel.columns}
    any_miss = any(v > 0 for v in miss.values())
    checks.append((
        "Zero missing in key funnel columns",
        not any_miss,
        f"missing={miss}" if any_miss else "no missing"))

    # (10) Cell count exactly 164,351 = 100 tags x 261 weeks x ... (sparse)
    cells = len(panel)
    ok = cells == 164351
    checks.append((
        "Panel cell count matches master panel (164,351)",
        ok, f"cells={cells:,}"))

    # Compose report
    lines = ["# Reusable Funnel Extension — Validation Report\n",
             f"_Generated: {datetime.now().isoformat(timespec='seconds')}_\n",
             "Each check below produces a hard pass/fail.\n",
             "If any check fails, downstream tables/figures must be revisited "
             "before submission.\n", "\n## Results\n"]
    all_passed = True
    for name, passed, detail in checks:
        lines.append(fmt_check(name, passed, detail))
        all_passed = all_passed and passed

    lines.append("\n## Summary")
    status = "ALL CHECKS PASSED" if all_passed else "SOME CHECKS FAILED"
    lines.append(f"\n**Overall status:** `{status}`")
    lines.append(f"\n**Checks run:** {len(checks)}  ")
    lines.append(f"**Passed:** {sum(1 for _, p, _ in checks if p)}  ")
    lines.append(f"**Failed:** {sum(1 for _, p, _ in checks if not p)}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[main] wrote {REPORT}")
    print(f"[main] overall: {status}")
    for name, passed, detail in checks:
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}] {name}")
        if detail and not passed:
            print(f"        detail: {detail}")


if __name__ == "__main__":
    main()
