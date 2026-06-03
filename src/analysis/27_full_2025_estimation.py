"""Decisive estimation on the FULL 100-tag 2020-2025 panel (replaces the
30-tag directional subset). Gate -> full DDD -> boundary-excluded ->
quarterly event study through 2025.
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

CHATGPT = pd.Timestamp("2022-11-30")
PANEL = PROCESSED_DIR / "panel_tag_week_question_type_2020_2025.csv"
MODELS = OUTPUTS_DIR / "models"
AI = "ai_answerability_structural"
BIN = 13


def prep(df):
    df = df.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["week_id"] = df["week_start"].dt.strftime("%Y-%m-%d")
    df["tagq"] = df["tag"].astype(str) + "::" + df["question_type"].astype(str)
    df["ai"] = df[AI].astype(float)
    df["s"] = df["substitutable_type"].astype(int)
    df["p"] = (df["week_start"] >= CHATGPT).astype(int)
    df["ai_post"] = df["ai"]*df["p"]; df["ai_sub"] = df["ai"]*df["s"]
    df["post_sub"] = df["p"]*df["s"]; df["ai_post_sub"] = df["ai"]*df["p"]*df["s"]
    return df


def ddd(df, lbl):
    m = pf.feols("log_questions_p1 ~ ai_post + ai_sub + post_sub + ai_post_sub "
                 "| tagq + week_id", data=df, vcov={"CRV1": "tag"})
    b = float(m.coef()["ai_post_sub"]); s = float(m.se()["ai_post_sub"]); p = float(m.pvalue()["ai_post_sub"])
    print(f"  {lbl}: beta={b:.4f} se={s:.4f} p={p:.4f} n={int(m._N)}", flush=True)
    return dict(spec=lbl, beta=b, se=s, p=p, n=int(m._N))


def event_study(df):
    d = df.copy()
    d["bin"] = ((d["week_start"] - CHATGPT).dt.days // 7) // BIN
    def nm(b): return f"bn{abs(b)}" if b < 0 else f"bp{b}"
    bins = sorted(b for b in d["bin"].unique() if b != -1)
    d["ai_sub_"] = d["ai"]*d["s"]
    for b in bins:
        d[nm(b)] = d["ai_sub_"]*(d["bin"] == b)
    terms = " + ".join(nm(b) for b in bins)
    m = pf.feols(f"log_questions_p1 ~ {terms} | tagq + week_id", data=d, vcov={"CRV1": "tag"})
    co = m.coef()
    return {int(b): float(co[nm(b)]) for b in bins if nm(b) in co}


def main():
    raw = pd.read_csv(PANEL)
    df = prep(raw)
    print(f"[panel] {len(df)} rows, {df['tag'].nunique()} tags, "
          f"weeks {df['week_start'].min().date()}..{df['week_start'].max().date()}", flush=True)

    print("\n[GATE] DDD on weeks < 2024-12-30 (must ~= -0.108):", flush=True)
    g = ddd(df[df["week_start"] < pd.Timestamp("2024-12-30")], "pre-2025 gate")
    if abs(g["beta"] - (-0.108)) > 0.03:
        print(f"  [WARN] gate off baseline by {g['beta']+0.108:.4f}", flush=True)
    else:
        print("  [gate] PASS", flush=True)

    rows = [g]
    print("\n[FULL 2020-2025]:", flush=True)
    rows.append(ddd(df, "full 2020-2025"))
    rows.append(ddd(df[df["question_type"] != "advanced_architecture"],
                    "full 2020-2025, boundary-excluded"))

    es = event_study(df)
    print("\n[event study, post-period bins]:", flush=True)
    for b in sorted(es):
        if b >= 0:
            yr = 2022 + (b*13+0)//52  # rough label
            print(f"   T+{b}: {es[b]:.3f}", flush=True)

    pd.DataFrame(rows).to_csv(MODELS / "full_2025_ddd.csv", index=False)
    pd.Series(es, name="beta").rename_axis("bin").to_csv(MODELS / "full_2025_eventstudy.csv")
    print("\n[done]", flush=True)


if __name__ == "__main__":
    main()
