"""
Bloque 1 — Construir Reusable Artifact Funnel panel.

Reutiliza la clasificacion question_type del master panel
(importando classify_questions, TAG_ALIASES, source_files desde
src.data.prepare_stackoverflow_question_type_raw) para garantizar
consistencia bit-a-bit con el panel ya validado.

Funnel a nivel pregunta:
    answered              = answer_count > 0
    accepted_answer       = has_accepted_answer == 1
    accepted_nonclosed    = accepted_answer & (is_closed == 0)
    accepted_nonnegative  = accepted_answer & (score >= 0)
    reusable_artifact     = accepted_answer & (score >= 0) & (is_closed == 0)

Agregado a panel (tag, week_start, question_type, substitutable_type).
Merge con ai_answerability_real.csv (4 medidas) y flag post_chatgpt
(week_start >= 2022-11-30).

Output: data/processed/reusable_artifact_funnel_panel.csv
Audit:  outputs/diagnostics/reusable_funnel_build_audit.md
"""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

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

CUTOFF = pd.Timestamp("2022-11-30")
PANEL_WEEK_MIN = pd.Timestamp("2020-01-06")  # alinea con master panel
RAW_SO_DIR = RAW_DIR / "stackoverflow"
OUTPUT_PANEL = PROCESSED_DIR / "reusable_artifact_funnel_panel.csv"
AUDIT_REPORT = OUTPUTS_DIR / "diagnostics" / "reusable_funnel_build_audit.md"
AI_ANSWERABILITY = PROCESSED_DIR / "ai_answerability_real.csv"

USECOLS = [
    "tag", "week_start", "question_id", "owner_user_id",
    "title", "body_length", "has_code",
    "score", "answer_count", "has_accepted_answer", "is_closed",
]

NUMERIC_COLS = [
    "question_id", "owner_user_id", "body_length",
    "has_code", "score", "answer_count",
    "has_accepted_answer", "is_closed",
]

FUNNEL_FLAGS = [
    "answered", "accepted_answer",
    "accepted_nonclosed", "accepted_nonnegative", "reusable_artifact",
]

GROUP_KEYS = ["tag", "week_start", "question_type", "substitutable_type"]


def add_funnel_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    ans = df["answer_count"].fillna(0)
    acc = (df["has_accepted_answer"].fillna(0) == 1)
    closed = (df["is_closed"].fillna(0) == 1)
    nonneg = (df["score"].fillna(0) >= 0)
    df["answered"] = (ans > 0).astype("int8")
    df["accepted_answer"] = acc.astype("int8")
    df["accepted_nonclosed"] = (acc & ~closed).astype("int8")
    df["accepted_nonnegative"] = (acc & nonneg).astype("int8")
    df["reusable_artifact"] = (acc & nonneg & ~closed).astype("int8")
    return df


def load_raw_all(files: list[Path]) -> tuple[pd.DataFrame, dict]:
    t0 = time.perf_counter()
    frames: list[pd.DataFrame] = []
    n_files = len(files)
    print(f"[load_raw_all] reading {n_files} files with usecols={len(USECOLS)}")
    for i, path in enumerate(files, start=1):
        frames.append(pd.read_csv(path, usecols=USECOLS))
        if i % 50 == 0 or i == n_files:
            print(f"  ... {i}/{n_files} files read")
    raw = pd.concat(frames, ignore_index=True)
    del frames
    pre_alias_rows = len(raw)
    raw["tag"] = raw["tag"].replace(TAG_ALIASES)
    pre_dedup_rows = len(raw)
    raw = raw.drop_duplicates(["question_id", "tag"]).reset_index(drop=True)
    post_dedup_rows = len(raw)
    raw["week_start"] = pd.to_datetime(raw["week_start"], errors="coerce")
    for col in NUMERIC_COLS:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    elapsed = time.perf_counter() - t0
    audit = {
        "files_loaded": n_files,
        "rows_pre_alias": pre_alias_rows,
        "rows_pre_dedup": pre_dedup_rows,
        "rows_post_dedup": post_dedup_rows,
        "rows_dropped_dedup": pre_dedup_rows - post_dedup_rows,
        "memory_mb": float(raw.memory_usage(deep=True).sum() / 1e6),
        "load_elapsed_s": round(elapsed, 1),
    }
    print(f"[load_raw_all] {audit}")
    return raw, audit


def build_funnel_panel(raw: pd.DataFrame) -> pd.DataFrame:
    print("[build_funnel_panel] classifying question_type ...")
    df = classify_questions(raw)
    print("[build_funnel_panel] adding funnel flags ...")
    df = add_funnel_flags(df)
    print("[build_funnel_panel] aggregating to panel cells ...")
    panel = (
        df.groupby(GROUP_KEYS, dropna=False)
        .agg(
            questions_count=("question_id", "nunique"),
            answered_questions=("answered", "sum"),
            accepted_answer_questions=("accepted_answer", "sum"),
            accepted_nonclosed_questions=("accepted_nonclosed", "sum"),
            accepted_nonnegative_questions=("accepted_nonnegative", "sum"),
            reusable_artifacts=("reusable_artifact", "sum"),
        )
        .reset_index()
    )
    panel = panel.sort_values(GROUP_KEYS).reset_index(drop=True)
    panel["week_start"] = pd.to_datetime(panel["week_start"], errors="coerce")
    n_before = len(panel)
    panel = panel[panel["week_start"] >= PANEL_WEEK_MIN].reset_index(drop=True)
    print(f"[build_funnel_panel] filtered week_start >= {PANEL_WEEK_MIN.date()}: "
          f"{n_before} -> {len(panel)} rows")
    return panel


def merge_answerability(panel: pd.DataFrame) -> pd.DataFrame:
    ai = pd.read_csv(AI_ANSWERABILITY)
    keep = [
        "tag",
        "ai_answerability_zscore",
        "ai_answerability_pca",
        "ai_answerability_quantile",
        "ai_answerability_structural",
    ]
    ai = ai[keep]
    merged = panel.merge(ai, on="tag", how="left", validate="m:1")
    return merged


def add_post_chatgpt(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    wk = pd.to_datetime(panel["week_start"], errors="coerce")
    panel["post_chatgpt"] = (wk >= CUTOFF).astype("int8")
    panel["post_chatgpt_bool"] = wk >= CUTOFF
    return panel


def validate_monotonicity(panel: pd.DataFrame) -> dict:
    checks = {}
    chain = [
        ("reusable_artifacts", "accepted_nonnegative_questions"),
        ("accepted_nonnegative_questions", "accepted_answer_questions"),
        ("accepted_nonclosed_questions", "accepted_answer_questions"),
        ("accepted_answer_questions", "answered_questions"),
        ("answered_questions", "questions_count"),
    ]
    for smaller, larger in chain:
        violations = int((panel[smaller] > panel[larger]).sum())
        checks[f"{smaller} <= {larger}"] = violations
    return checks


def main() -> None:
    print(f"[main] start {datetime.now().isoformat(timespec='seconds')}")
    files = source_files(RAW_SO_DIR, year=None)
    print(f"[main] {len(files)} raw files matched by source_files()")
    raw, load_audit = load_raw_all(files)
    panel = build_funnel_panel(raw)
    del raw  # free memory before merges
    audit = dict(load_audit)
    audit["panel_rows_after_groupby"] = len(panel)
    audit["panel_unique_tags"] = int(panel["tag"].nunique())
    audit["panel_unique_question_types"] = int(panel["question_type"].nunique())
    audit["panel_unique_weeks"] = int(panel["week_start"].nunique())
    audit["panel_week_min"] = str(pd.to_datetime(panel["week_start"]).min().date())
    audit["panel_week_max"] = str(pd.to_datetime(panel["week_start"]).max().date())
    audit["total_questions_count"] = int(panel["questions_count"].sum())
    audit["total_answered"] = int(panel["answered_questions"].sum())
    audit["total_accepted"] = int(panel["accepted_answer_questions"].sum())
    audit["total_accepted_nonclosed"] = int(panel["accepted_nonclosed_questions"].sum())
    audit["total_accepted_nonneg"] = int(panel["accepted_nonnegative_questions"].sum())
    audit["total_reusable"] = int(panel["reusable_artifacts"].sum())

    monot = validate_monotonicity(panel)
    audit["monotonicity_violations"] = monot
    total_violations = sum(monot.values())
    if total_violations > 0:
        print(f"[main] ⚠️ {total_violations} monotonicity violations detected!")

    print("[main] merging with AI answerability ...")
    panel = merge_answerability(panel)
    audit["after_merge_rows"] = len(panel)
    miss_ai = int(panel["ai_answerability_structural"].isna().sum())
    audit["rows_missing_answerability"] = miss_ai

    print("[main] adding post_chatgpt flag ...")
    panel = add_post_chatgpt(panel)
    n_post = int(panel["post_chatgpt"].sum())
    n_pre = int((panel["post_chatgpt"] == 0).sum())
    audit["panel_cells_pre"] = n_pre
    audit["panel_cells_post"] = n_post

    OUTPUT_PANEL.parent.mkdir(parents=True, exist_ok=True)
    print(f"[main] writing {OUTPUT_PANEL}")
    panel.to_csv(OUTPUT_PANEL, index=False)
    audit["output_path"] = str(OUTPUT_PANEL)
    audit["output_size_mb"] = round(OUTPUT_PANEL.stat().st_size / 1e6, 2)

    AUDIT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Reusable Funnel — Build Audit\n",
             f"_Generated: {datetime.now().isoformat(timespec='seconds')}_\n\n",
             "## Audit metrics\n"]
    for k, v in audit.items():
        if k == "monotonicity_violations":
            lines.append(f"- **{k}**:")
            for sub, count in v.items():
                emoji = "✅" if count == 0 else "❌"
                lines.append(f"  - {emoji} `{sub}` violations: {count}")
        else:
            lines.append(f"- **{k}**: {v}")
    lines.append("\n## First 5 rows of output panel\n")
    lines.append(panel.head(5).to_markdown(index=False))
    AUDIT_REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[main] audit written to {AUDIT_REPORT}")
    print(f"[main] done {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
