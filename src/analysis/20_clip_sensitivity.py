"""Action 4: clip sensitivity of the voting-baseline rescaling.

Re-runs the voting-normalised high-value DDD under four clip ranges for
the pre/post mean-abs-score ratio: no clip, [0.3, 5.0], [0.5, 3.0]
(the value used in the main text), and [0.7, 2.0]. Reloads the raw
question stream (reuses the canonical classify_questions, Rule 2).

The point is to show whether the one estimate that depends on the
rescaling -- the elite tail (score>=5) -- is fragile to the clip choice,
while the low thresholds (score>=1, >=2) are essentially invariant.

Output: outputs/models/clip_sensitivity.csv,
        outputs/tables/table_clip_sensitivity.tex
"""
from __future__ import annotations
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd
import pyfixest as pf

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.paths import OUTPUTS_DIR, PROCESSED_DIR, RAW_DIR  # noqa: E402
from src.data.prepare_stackoverflow_question_type_raw import (  # noqa: E402
    TAG_ALIASES, classify_questions,
)

CHATGPT = pd.Timestamp("2022-11-30")
PANEL_WEEK_MIN = pd.Timestamp("2020-01-06")
RAW_SO = RAW_DIR / "stackoverflow"
AI_REAL = PROCESSED_DIR / "ai_answerability_real.csv"
AI_VAR = "ai_answerability_structural"
MODELS = OUTPUTS_DIR / "models"; TABLES = OUTPUTS_DIR / "tables"
USECOLS = ["tag", "week_start", "question_id", "owner_user_id", "title",
           "body_length", "has_code", "score", "answer_count",
           "has_accepted_answer", "is_closed"]
CLIPS = [("no clip", None), ("[0.3, 5.0]", (0.3, 5.0)),
         ("[0.5, 3.0] (main)", (0.5, 3.0)), ("[0.7, 2.0]", (0.7, 2.0))]


def load_raw_all():
    t0 = time.perf_counter()
    files = sorted(RAW_SO.glob("stackoverflow_question_type_raw_*.csv"))
    print(f"[load_raw] {len(files)} files", flush=True)
    frames = []
    for i, f in enumerate(files, 1):
        frames.append(pd.read_csv(f, usecols=USECOLS))
        if i % 100 == 0:
            print(f"  ... {i}/{len(files)}", flush=True)
    raw = pd.concat(frames, ignore_index=True)
    raw["tag"] = raw["tag"].replace(TAG_ALIASES)
    raw = raw.drop_duplicates(["question_id", "tag"]).reset_index(drop=True)
    raw["week_start"] = pd.to_datetime(raw["week_start"], errors="coerce")
    for c in ["question_id", "body_length", "has_code", "score",
              "answer_count", "has_accepted_answer", "is_closed"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    print(f"[load_raw] {len(raw):,} rows; {time.perf_counter()-t0:.0f}s",
          flush=True)
    return raw


def build_panel(df0, clip):
    df = classify_questions(df0)
    acc = (df["has_accepted_answer"].fillna(0) == 1)
    closed = (df["is_closed"].fillna(0) == 1)
    base = acc & ~closed
    score = df["score"].fillna(0).astype(float)
    tmp = df.assign(abs_score=score.abs(),
                    is_post=(df["week_start"] >= CHATGPT))
    tm = tmp.groupby(["tag", "is_post"])["abs_score"].mean().unstack(fill_value=np.nan)
    if True in tm.columns and False in tm.columns:
        ratio = tm[False] / tm[True].replace(0, np.nan)
        ratio = ratio.replace([np.inf, -np.inf], np.nan).fillna(1.0)
        if clip is not None:
            ratio = ratio.clip(clip[0], clip[1])
        tmp = tmp.merge(ratio.rename("vr").reset_index(), on="tag", how="left")
        scale = np.where(tmp["is_post"], tmp["vr"], 1.0)
        score = score * scale
    flags = {}
    for k in [1, 2, 5]:
        flags[f"hv_{k}"] = (base & (score >= k)).astype("int8")
    for c, f in flags.items():
        df[c] = f
    panel = (df.groupby(["tag", "week_start", "question_type",
                         "substitutable_type"], dropna=False)
             .agg(**{c: (c, "sum") for c in flags}).reset_index())
    panel["week_start"] = pd.to_datetime(panel["week_start"])
    panel = panel[panel["week_start"] >= PANEL_WEEK_MIN].reset_index(drop=True)
    ai = pd.read_csv(AI_REAL)[["tag", AI_VAR]]
    panel = panel.merge(ai, on="tag", how="left", validate="m:1")
    panel["post"] = (panel["week_start"] >= CHATGPT).astype(int)
    return panel


def fit(panel, ycol):
    w = panel.copy()
    w["tag_qtype"] = w["tag"].astype(str) + "::" + w["question_type"].astype(str)
    w["week_id"] = w["week_start"].dt.strftime("%Y-%m-%d")
    w["ai"] = w[AI_VAR].astype(float); w["sub"] = w["substitutable_type"].astype(int)
    w["ai_post"] = w["ai"]*w["post"]; w["ai_sub"] = w["ai"]*w["sub"]
    w["post_sub"] = w["post"]*w["sub"]; w["ai_post_sub"] = w["ai"]*w["post"]*w["sub"]
    w["log_y"] = np.log1p(w[ycol])
    m = pf.feols("log_y ~ ai_post + ai_sub + post_sub + ai_post_sub "
                 "| tag_qtype + week_id", data=w, vcov={"CRV1": "tag"})
    return (float(m.coef()["ai_post_sub"]), float(m.se()["ai_post_sub"]),
            float(m.pvalue()["ai_post_sub"]))


def main():
    raw = load_raw_all()
    rows = []
    for label, clip in CLIPS:
        panel = build_panel(raw, clip)
        rec = {"clip": label}
        for k in [1, 2, 5]:
            b, s, p = fit(panel, f"hv_{k}")
            rec[f"k{k}_beta"] = b; rec[f"k{k}_p"] = p
            print(f"  clip {label} k={k}: beta={b:.4f} p={p:.4f}", flush=True)
        rows.append(rec)
    out = pd.DataFrame(rows)
    out.to_csv(MODELS / "clip_sensitivity.csv", index=False)
    lines = [r"\begin{table}[ht]", r"\centering",
        r"\caption{Sensitivity of the voting-baseline-rescaled high-value "
        r"DDD to the clip range applied to the pre/post mean-absolute-score "
        r"ratio. The low thresholds (score $\geq 1$, $\geq 2$) are stable "
        r"across clip choices; only the elite tail (score $\geq 5$), which "
        r"is the single estimate that depends on the rescaling, moves with "
        r"the clip, confirming that the elite-tail result is the fragile "
        r"one and the headline gradient is not.}",
        r"\label{tab:clip_sensitivity}", r"\small",
        r"\begin{tabular}{lrrr}", r"\toprule",
        r"Clip range & score $\geq 1$ & score $\geq 2$ & score $\geq 5$ \\",
        r"\midrule"]
    for _, r in out.iterrows():
        def cell(k):
            star = "^{*}" if r[f"k{k}_p"] < 0.05 else ""
            return f"${r[f'k{k}_beta']:.3f}{star}$"
        lines.append(f"{r['clip']} & {cell(1)} & {cell(2)} & {cell(5)} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}",
              r"\\[2pt]\footnotesize $^{*}$ $p<0.05$ (tag-clustered).",
              r"\end{table}"]
    (TABLES / "table_clip_sensitivity.tex").write_text("\n".join(lines), encoding="utf-8")
    print("[done] clip sensitivity", flush=True)


if __name__ == "__main__":
    main()
