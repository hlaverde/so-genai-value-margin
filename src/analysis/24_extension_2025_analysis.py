"""Analyse the 2025 extension: does the within-tag association persist
into 2025 (dissolving the late-emergence concern), and does the monitor's
disproportionality persist with genuinely new data?

Runs on the stratified subset fetched by fetch_2025_extension.py, so all
estimates are on that subset; the comparison is within-subset
(2020-2024 vs 2020-2025) so the subset restriction does not confound it.
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
from scipy.stats import spearmanr  # noqa: E402

CHATGPT = pd.Timestamp("2022-11-30")
MASTER = PROCESSED_DIR / "stackoverflow_question_type_master_panel.csv"
VW = PROCESSED_DIR / "value_weighted_funnel_panel.csv"
AI_REAL = PROCESSED_DIR / "ai_answerability_real.csv"
RAW25 = PROCESSED_DIR / "so_2025_extension_raw.csv"
MODELS = OUTPUTS_DIR / "models"; TABLES = OUTPUTS_DIR / "tables"
AI = "ai_answerability_structural"
NONSUB = {"version_environment_specific", "advanced_architecture"}
BIN = 13


def build_2025_panel():
    raw = pd.read_csv(RAW25)
    raw["week_start"] = pd.to_datetime(raw["week_start"])
    for c in ["question_id", "body_length", "has_code", "score",
              "answer_count", "has_accepted_answer", "is_closed"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    df = classify_questions(raw)
    df["substitutable_type"] = (~df["question_type"].isin(NONSUB)).astype(int)
    acc = df["has_accepted_answer"].fillna(0) == 1
    clo = df["is_closed"].fillna(0) == 1
    df["hv"] = (acc & ~clo & (df["score"].fillna(0) >= 1)).astype(int)
    p = (df.groupby(["tag", "week_start", "question_type", "substitutable_type"])
         .agg(questions=("question_id", "nunique"), hv=("hv", "sum")).reset_index())
    ai = pd.read_csv(AI_REAL)[["tag", AI]]
    return p.merge(ai, on="tag", how="left")


def assign_bin(w):
    return ((w - CHATGPT).dt.days // 7) // BIN


def fit_ddd(df):
    d = df.copy()
    d["week_id"] = d["week_start"].dt.strftime("%Y-%m-%d")
    d["tag_qtype"] = d["tag"].astype(str) + "::" + d["question_type"].astype(str)
    d["ai"] = d[AI].astype(float); d["sub"] = d["substitutable_type"].astype(int)
    d["post"] = (d["week_start"] >= CHATGPT).astype(int)
    d["ai_post"] = d["ai"]*d["post"]; d["ai_sub"] = d["ai"]*d["sub"]
    d["post_sub"] = d["post"]*d["sub"]; d["ai_post_sub"] = d["ai"]*d["post"]*d["sub"]
    d["log_y"] = np.log1p(d["questions"])
    m = pf.feols("log_y ~ ai_post + ai_sub + post_sub + ai_post_sub "
                 "| tag_qtype + week_id", data=d, vcov={"CRV1": "tag"})
    return float(m.coef()["ai_post_sub"]), float(m.se()["ai_post_sub"]), float(m.pvalue()["ai_post_sub"])


def event_study(df):
    d = df.copy()
    d["bin"] = assign_bin(d["week_start"])
    d["week_id"] = d["week_start"].dt.strftime("%Y-%m-%d")
    d["tag_qtype"] = d["tag"].astype(str) + "::" + d["question_type"].astype(str)
    d["ai_sub"] = d[AI].astype(float) * d["substitutable_type"].astype(int)
    def nm(b):
        return f"bn{abs(b)}" if b < 0 else f"bp{b}"
    bins = sorted(b for b in d["bin"].unique() if b != -1)
    for b in bins:
        d[nm(b)] = d["ai_sub"] * (d["bin"] == b)
    terms = " + ".join(nm(b) for b in bins)
    d["log_y"] = np.log1p(d["questions"])
    m = pf.feols(f"log_y ~ {terms} | tag_qtype + week_id", data=d, vcov={"CRV1": "tag"})
    co = m.coef()
    return {b: float(co[nm(b)]) for b in bins if nm(b) in co}


def main():
    p25 = build_2025_panel()
    # keep only the QUERIED subset tags (others are incidental co-occurring
    # tags, incompletely sampled, and would bias the panel)
    queried = set(pick_subset())
    p25 = p25[p25["tag"].isin(queried)].reset_index(drop=True)
    subset = sorted(p25["tag"].unique())
    print(f"[2025] panel (queried subset): {len(p25)} cells, "
          f"{len(subset)} tags, {p25['questions'].sum():,.0f} questions",
          flush=True)

    master = pd.read_csv(MASTER)
    master["week_start"] = pd.to_datetime(master["week_start"])
    m = master[master["tag"].isin(subset)][
        ["tag", "week_start", "question_type", "substitutable_type",
         "questions", AI]].copy()
    p25c = p25[["tag", "week_start", "question_type", "substitutable_type",
                "questions", AI]]
    combined = pd.concat([m, p25c], ignore_index=True)

    # DDD: subset 2020-2024 vs 2020-2025
    b24, s24, p24 = fit_ddd(m)
    b25, s25, p25v = fit_ddd(combined)
    print(f"[DDD] subset 2020-2024: {b24:.4f} (se {s24:.4f}, p {p24:.3f})", flush=True)
    print(f"[DDD] subset 2020-2025: {b25:.4f} (se {s25:.4f}, p {p25v:.3f})", flush=True)

    # event study extended
    es = event_study(combined)
    print("[event study] post-period bins (T+k):", flush=True)
    for b in sorted(es):
        if b >= 0:
            print(f"   T+{b}: {es[b]:.3f}", flush=True)

    # monitor persistence with NEW 2025 data
    vw = pd.read_csv(VW); vw["week_start"] = pd.to_datetime(vw["week_start"])
    vw = vw[vw["tag"].isin(subset)]
    def drops(panel_q, panel_hv_pre, panel_hv_yr):
        pass
    # per-tag: pre baseline (2020-2022), 2024 hv, 2025 hv
    vw["yr"] = vw["week_start"].dt.year
    pre = vw[vw["week_start"] < CHATGPT].groupby("tag").agg(
        q=("questions_count", "sum"), hv=("high_value_artifacts", "sum"),
        nw=("week_start", "nunique"))
    y24 = vw[vw["yr"] == 2024].groupby("tag").agg(
        hv=("high_value_artifacts", "sum"), nw=("week_start", "nunique"))
    hv25 = p25.groupby("tag").agg(hv=("hv", "sum"),
                                  nw=("week_start", "nunique"))
    tags = [t for t in subset if t in pre.index and t in y24.index and t in hv25.index]
    rows = []
    for t in tags:
        base_hv = pre.loc[t, "hv"] / pre.loc[t, "nw"]
        if base_hv <= 0:
            continue
        d24 = 1 - (y24.loc[t, "hv"] / y24.loc[t, "nw"]) / base_hv
        d25 = 1 - (hv25.loc[t, "hv"] / hv25.loc[t, "nw"]) / base_hv
        rows.append({"tag": t, "hv_drop_2024": d24, "hv_drop_2025": d25})
    pm = pd.DataFrame(rows)
    rho, pp = spearmanr(pm["hv_drop_2024"], pm["hv_drop_2025"])
    print(f"[monitor persistence] Spearman(hv_drop 2024, hv_drop 2025) = "
          f"{rho:.3f} (p={pp:.3f}, n={len(pm)})", flush=True)

    pd.DataFrame([{"ddd_2024": b24, "p_2024": p24, "ddd_2025": b25,
                   "p_2025": p25v, "n_tags": len(subset),
                   "persistence_rho": rho}]).to_csv(
        MODELS / "extension_2025_summary.csv", index=False)
    pd.Series(es).to_csv(MODELS / "extension_2025_eventstudy.csv")
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
