"""Corrected A6 (late-arrival confounders via pre-event subsample) and
A7 (AUC by proper answerability quartile)."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pyfixest as pf

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.paths import PROCESSED_DIR, OUTPUTS_DIR  # noqa: E402

CHATGPT = pd.Timestamp("2022-11-30")
MASTER = PROCESSED_DIR / "stackoverflow_question_type_master_panel.csv"
QVAL = PROCESSED_DIR / "ai_answerability_revealed_validation_question.csv"
MODELS = OUTPUTS_DIR / "models"; TABLES = OUTPUTS_DIR / "tables"
AI = "ai_answerability_structural"


def fit_triple(df, end=None):
    w = df.copy()
    if end is not None:
        w = w[w["week_start"] < end]
    w["week_id"] = w["week_start"].dt.strftime("%Y-%m-%d")
    w["ai"] = w[AI].astype(float); w["sub"] = w["substitutable_type"].astype(int)
    w["post"] = (w["week_start"] >= CHATGPT).astype(int)
    w["tag_qtype"] = w["tag"].astype(str) + "::" + w["question_type"].astype(str)
    w["ai_post"] = w["ai"]*w["post"]; w["ai_sub"] = w["ai"]*w["sub"]
    w["post_sub"] = w["post"]*w["sub"]; w["ai_post_sub"] = w["ai"]*w["post"]*w["sub"]
    w["log_y"] = np.log1p(w["questions"])
    m = pf.feols("log_y ~ ai_post + ai_sub + post_sub + ai_post_sub "
                 "| tag_qtype + week_id", data=w, vcov={"CRV1": "tag"})
    return (float(m.coef()["ai_post_sub"]), float(m.se()["ai_post_sub"]),
            float(m.pvalue()["ai_post_sub"]), int(m._N))


def a6():
    print("[A6] pre-event subsample test")
    df = pd.read_csv(MASTER); df["week_start"] = pd.to_datetime(df["week_start"])
    specs = [
        ("Full sample (post = Nov 2022 -- Dec 2024)", None),
        ("Ends before moderation strike (2023-06-05)", pd.Timestamp("2023-06-05")),
        ("Ends before SO--OpenAI licence (2024-05-06)", pd.Timestamp("2024-05-06")),
    ]
    rows = []
    for lab, end in specs:
        b, s, p, n = fit_triple(df, end)
        rows.append({"spec": lab, "beta": b, "se": s, "p": p, "n": n})
        print(f"  {lab}: beta={b:.4f} se={s:.4f} p={p:.4f} n={n}")
    out = pd.DataFrame(rows); out.to_csv(MODELS / "late_confounders.csv", index=False)
    lines = [r"\begin{table}[ht]", r"\centering",
        r"\caption{Robustness to late-arriving confounders. The displacement "
        r"is already negative in the window that ends \emph{before} the "
        r"mid-2023 moderation strike and again before the May 2024 "
        r"OpenAI licence, so neither event can account for it; the "
        r"December 2022 AI-content ban is essentially coincident with the "
        r"cutoff and cannot be separately identified. Read with the smooth, "
        r"non-jumping event-study trajectory (Figure~\ref{fig:event_study}).}",
        r"\label{tab:late_confounders}", r"\small",
        r"\begin{tabular}{lrrr}", r"\toprule",
        r"Sample window & $\hat\beta_{\text{DDD}}$ & SE & $p$ \\", r"\midrule"]
    for r in rows:
        lines.append(f"{r['spec']} & {r['beta']:.4f} & {r['se']:.4f} & {r['p']:.4f} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (TABLES / "table_late_confounders.tex").write_text("\n".join(lines), encoding="utf-8")


def a7():
    print("[A7] AUC by answerability quartile (qcut)")
    from sklearn.metrics import roc_auc_score
    df = pd.read_csv(QVAL, usecols=["tag", "revealed_high_answerability", AI])
    df = df.dropna(subset=["revealed_high_answerability", AI])
    overall = roc_auc_score(df["revealed_high_answerability"], df[AI])
    df["q"] = pd.qcut(df[AI], 4, labels=[1, 2, 3, 4], duplicates="drop")
    rows = [{"stratum": "Overall", "auc": overall, "n": len(df)}]
    print(f"  overall AUC={overall:.4f} n={len(df):,}")
    for q in [1, 2, 3, 4]:
        sub = df[df["q"] == q]
        if sub["revealed_high_answerability"].nunique() < 2:
            continue
        a = roc_auc_score(sub["revealed_high_answerability"], sub[AI])
        rows.append({"stratum": f"Answerability quartile {q}", "auc": a, "n": len(sub)})
        print(f"  Q{q}: AUC={a:.4f} n={len(sub):,}")
    out = pd.DataFrame(rows); out.to_csv(MODELS / "auc_by_stratum.csv", index=False)
    lines = [r"\begin{table}[ht]", r"\centering",
        r"\caption{Question-level discrimination of the tag-level "
        r"answerability proxy for revealed high answerability, overall and "
        r"by pre-treatment answerability quartile. The proxy is a coarse, "
        r"tag-level instrument and is weak at the individual-question "
        r"level (AUC near 0.5--0.57 throughout); we report the stratified "
        r"values rather than the pooled AUC alone so the reader can see "
        r"that the instrument carries tag-level, not question-level, "
        r"signal.}",
        r"\label{tab:auc_stratum}", r"\small",
        r"\begin{tabular}{lrr}", r"\toprule",
        r"Stratum & AUC & $N$ \\", r"\midrule"]
    for r in rows:
        lines.append(f"{r['stratum']} & {r['auc']:.3f} & {int(r['n']):,} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (TABLES / "table_auc_stratum.tex").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    a6(); a7()
    print("[done]")
