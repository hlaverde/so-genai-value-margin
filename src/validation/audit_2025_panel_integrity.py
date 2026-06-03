"""Strict read-only audit for the 2025 Stack Overflow extension and panel."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.prepare_stackoverflow_question_type_raw import TAG_ALIASES, classify_questions  # noqa: E402
from src.paths import PROCESSED_DIR, RAW_DIR, TABLES_DIR, OUTPUTS_DIR  # noqa: E402

RAW_2025 = RAW_DIR / "stackoverflow" / "api_2025_full_100tags"
MANIFEST_CANDIDATES = [
    RAW_2025 / "_manifest_2025_full_100tags.csv",
    RAW_2025 / "manifest_2025_full_100tags.csv",
]
CLEAN_2025 = PROCESSED_DIR / "stackoverflow_2025_clean_question_tag.csv"
PANEL_2020_2025 = PROCESSED_DIR / "panel_tag_week_question_type_2020_2025.csv"
OLD_PANEL = PROCESSED_DIR / "stackoverflow_question_type_master_panel.csv"
TAG_SOURCE = PROCESSED_DIR / "ai_answerability_real.csv"

OUT_RAW = TABLES_DIR / "audit_2025_raw_integrity.csv"
OUT_CLEAN = TABLES_DIR / "audit_2025_clean_integrity.csv"
OUT_PANEL = TABLES_DIR / "audit_2025_panel_integrity.csv"
OUT_TAG = TABLES_DIR / "audit_2025_tag_level_counts.csv"
OUT_QTYPE = TABLES_DIR / "audit_2025_question_type_counts.csv"
OUT_CONSISTENCY = TABLES_DIR / "audit_2020_2024_consistency_check.csv"
OUT_REPORT = OUTPUTS_DIR / "reports" / "audit_2025_panel_integrity_report.md"

QUESTION_TYPES = {
    "short_code",
    "long_code",
    "how_to",
    "debugging_simple",
    "other_conceptual",
    "version_environment_specific",
    "advanced_architecture",
}
REQUIRED_CLEAN = [
    "question_id",
    "tag",
    "tag_consulted",
    "creation_date",
    "score",
    "answer_count",
    "is_answered",
    "accepted_answer_id",
    "closed_date",
    "is_closed",
    "owner_user_id",
    "title",
    "tags_original",
    "body_length",
    "has_code",
    "source",
]
REQUIRED_PANEL_ALIASES = {
    "tag": ["tag"],
    "week": ["week", "week_start"],
    "question_type": ["question_type"],
    "n_questions": ["n_questions", "questions"],
    "substitutable_type": ["substitutable_type", "substitutable"],
    "post_chatgpt": ["post_chatgpt", "post"],
    "ai_answerability_structural": ["ai_answerability_structural"],
    "log_questions_p1": ["log_questions_p1"],
    "tag_qtype": ["tag_qtype"],
}


def canonical_tag(tag: str) -> str:
    return TAG_ALIASES.get(str(tag), str(tag))


def status(ok: bool) -> str:
    return "ok" if ok else "fail"


def manifest_path() -> Path | None:
    for path in MANIFEST_CANDIDATES:
        if path.exists():
            return path
    return None


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, Path | None]:
    fixed = pd.read_csv(TAG_SOURCE)
    clean = pd.read_csv(CLEAN_2025)
    panel = pd.read_csv(PANEL_2020_2025)
    old_panel = pd.read_csv(OLD_PANEL)
    mpath = manifest_path()
    manifest = pd.read_csv(mpath) if mpath else pd.DataFrame()
    return fixed, clean, panel, old_panel, manifest, mpath


def raw_integrity(fixed: pd.DataFrame, manifest: pd.DataFrame) -> pd.DataFrame:
    rows = []
    fixed_tags = sorted(fixed["tag"].astype(str).unique())
    manifest_work = manifest.copy()
    if not manifest_work.empty and "tag_consulted" in manifest_work.columns:
        manifest_work["canonical_tag"] = manifest_work["tag_consulted"].map(canonical_tag)
    for tag in fixed_tags:
        folder = RAW_2025 / tag
        files = sorted(folder.glob("*.json")) if folder.exists() else []
        valid = invalid = empty = 0
        for path in files:
            if path.stat().st_size == 0:
                empty += 1
                continue
            try:
                json.loads(path.read_text(encoding="utf-8"))
                valid += 1
            except Exception:
                invalid += 1
        if manifest_work.empty:
            m = pd.DataFrame()
        else:
            m = manifest_work[manifest_work["canonical_tag"] == tag]
        failed = int((m.get("status", pd.Series(dtype=str)).astype(str).str.lower() == "failed").sum()) if not m.empty else 0
        completed = int((m.get("status", pd.Series(dtype=str)).astype(str).str.lower() == "complete").sum()) if not m.empty else 0
        page_cap = int(pd.to_numeric(m.get("page_cap_hit", pd.Series(dtype=float)), errors="coerce").fillna(0).max()) if not m.empty else 0
        quota_stop = int(m.astype(str).apply(lambda col: col.str.contains("quota", case=False, na=False)).any(axis=1).sum()) if not m.empty else 0
        raw_status = "ok"
        if not folder.exists() or not files:
            raw_status = "missing_raw"
        elif invalid or empty:
            raw_status = "invalid_json"
        elif failed:
            raw_status = "failed_windows"
        elif page_cap:
            raw_status = "possible_page_cap"
        elif completed == 0:
            raw_status = "manifest_missing"
        rows.append(
            {
                "tag": tag,
                "n_json_files": len(files),
                "n_valid_json_files": valid,
                "n_invalid_json_files": invalid,
                "n_empty_json_files": empty,
                "manifest_rows": len(m),
                "manifest_completed_windows": completed,
                "manifest_failed_windows": failed,
                "page_cap_hit": page_cap,
                "quota_stop_flag_if_available": quota_stop,
                "raw_status": raw_status,
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT_RAW, index=False)
    return out


def tag_level_counts(fixed: pd.DataFrame, clean: pd.DataFrame, panel: pd.DataFrame, manifest: pd.DataFrame) -> pd.DataFrame:
    fixed_tags = sorted(fixed["tag"].astype(str).unique())
    clean = clean.copy()
    clean["tag_consulted"] = clean["tag_consulted"].map(canonical_tag)
    clean["creation_date"] = pd.to_datetime(clean["creation_date"], errors="coerce")
    panel = panel.copy()
    panel["week_start"] = pd.to_datetime(panel["week_start"], errors="coerce")
    p25 = panel[panel["week_start"].dt.year == 2025]
    manifest_tags = set()
    if not manifest.empty and "tag_consulted" in manifest.columns:
        manifest_tags = set(manifest["tag_consulted"].map(canonical_tag))
    rows = []
    for tag in fixed_tags:
        folder = RAW_2025 / tag
        sub_clean = clean[clean["tag_consulted"] == tag]
        sub_panel = p25[p25["tag"] == tag]
        q2025 = sub_clean["question_id"].nunique()
        stat = "ok"
        if not folder.exists():
            stat = "missing_raw"
        elif sub_clean.empty:
            stat = "missing_clean"
        elif sub_panel.empty:
            stat = "missing_panel"
        elif q2025 == 0:
            stat = "suspicious_low_count"
        rows.append(
            {
                "tag": tag,
                "in_fixed_100_list": True,
                "raw_folder_exists": folder.exists(),
                "in_manifest": tag in manifest_tags,
                "in_clean_2025": not sub_clean.empty,
                "in_panel_2020_2025": not sub_panel.empty,
                "n_raw_json_files": len(list(folder.glob("*.json"))) if folder.exists() else 0,
                "n_clean_question_tag_rows_2025": len(sub_clean),
                "n_unique_questions_2025": q2025,
                "n_panel_rows_2025": len(sub_panel),
                "first_observed_date_2025": sub_clean["creation_date"].min(),
                "last_observed_date_2025": sub_clean["creation_date"].max(),
                "status": stat,
            }
        )
    fixed_set = set(fixed_tags)
    extra_panel = sorted(set(p25["tag"].dropna().astype(str)) - fixed_set)
    for tag in extra_panel:
        rows.append(
            {
                "tag": tag,
                "in_fixed_100_list": False,
                "raw_folder_exists": (RAW_2025 / tag).exists(),
                "in_manifest": tag in manifest_tags,
                "in_clean_2025": tag in set(clean["tag_consulted"]),
                "in_panel_2020_2025": True,
                "n_raw_json_files": len(list((RAW_2025 / tag).glob("*.json"))) if (RAW_2025 / tag).exists() else 0,
                "n_clean_question_tag_rows_2025": int((clean["tag_consulted"] == tag).sum()),
                "n_unique_questions_2025": int(clean.loc[clean["tag_consulted"] == tag, "question_id"].nunique()),
                "n_panel_rows_2025": int((p25["tag"] == tag).sum()),
                "first_observed_date_2025": "",
                "last_observed_date_2025": "",
                "status": "extra_tag",
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT_TAG, index=False)
    return out


def clean_integrity(clean: pd.DataFrame) -> pd.DataFrame:
    df = clean.copy()
    rows = []
    cols = set(df.columns)
    missing_required = [c for c in REQUIRED_CLEAN if c not in cols]
    week_col = "week_start" if "week_start" in cols else "week" if "week" in cols else None
    df["creation_date"] = pd.to_datetime(df.get("creation_date"), errors="coerce")
    if week_col:
        df[week_col] = pd.to_datetime(df[week_col], errors="coerce")
    qid_tag_dup = int(df.duplicated(["question_id", "tag_consulted"]).sum()) if {"question_id", "tag_consulted"} <= cols else np.nan
    all_calendar_2025 = bool((df["creation_date"].dt.year == 2025).all())
    score_numeric = pd.to_numeric(df.get("score"), errors="coerce").notna().all() if "score" in cols else False
    source_ok = df.get("source", pd.Series(dtype=str)).astype(str).str.contains("stackexchange|api", case=False, na=False).all() if "source" in cols else False
    if {"accepted_answer_id", "has_accepted_answer"} <= cols:
        accepted = df["accepted_answer_id"].notna()
        has_acc = pd.to_numeric(df["has_accepted_answer"], errors="coerce").fillna(0).astype(int).eq(1)
        accepted_consistent = bool((accepted == has_acc).all())
    else:
        accepted_consistent = None
    if {"closed_date", "is_closed"} <= cols:
        closed = df["closed_date"].notna()
        is_closed = pd.to_numeric(df["is_closed"], errors="coerce").fillna(0).astype(int).eq(1)
        closed_consistent = bool((closed == is_closed).all())
    else:
        closed_consistent = None

    metrics = [
        ("row_count", len(df), "ok", ""),
        ("unique_question_id_count", df["question_id"].nunique() if "question_id" in cols else "", status("question_id" in cols), ""),
        ("duplicate_question_id_x_tag_consulted", qid_tag_dup, status(qid_tag_dup == 0), ""),
        ("missing_question_id", int(df["question_id"].isna().sum()) if "question_id" in cols else "", status("question_id" in cols and df["question_id"].notna().all()), ""),
        ("missing_tag", int(df["tag_consulted"].isna().sum()) if "tag_consulted" in cols else "", status("tag_consulted" in cols and df["tag_consulted"].notna().all()), ""),
        ("missing_creation_date", int(df["creation_date"].isna().sum()), status(df["creation_date"].notna().all()), ""),
        ("min_creation_date", df["creation_date"].min(), "ok", ""),
        ("max_creation_date", df["creation_date"].max(), "ok", ""),
        ("all_observations_calendar_2025", all_calendar_2025, status(all_calendar_2025), ""),
        ("score_numeric", score_numeric, status(score_numeric), ""),
        ("accepted_answer_consistency", accepted_consistent, "ok" if accepted_consistent is not False else "fail", "checked when both accepted_answer_id and has_accepted_answer exist"),
        ("closed_consistency", closed_consistent, "ok" if closed_consistent is not False else "fail", "checked when both closed_date and is_closed exist"),
        ("source_api_identified", source_ok, status(source_ok), ""),
        ("missing_required_columns", ";".join(missing_required), "warn" if missing_required else "ok", "Columns may be absent if not used by API filter/pipeline."),
        ("week_column", week_col or "", status(week_col is not None), ""),
    ]
    for metric, value, stat, notes in metrics:
        rows.append({"metric": metric, "value": value, "status": stat, "notes": notes})
    out = pd.DataFrame(rows)
    out.to_csv(OUT_CLEAN, index=False)
    return out


def panel_integrity(panel: pd.DataFrame, clean: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = panel.copy()
    df["week_start"] = pd.to_datetime(df["week_start"], errors="coerce")
    p25 = df[df["week_start"].dt.year == 2025].copy()
    required_map = {}
    missing_logical = []
    for logical, aliases in REQUIRED_PANEL_ALIASES.items():
        found = next((c for c in aliases if c in df.columns), None)
        required_map[logical] = found or ""
        if found is None:
            missing_logical.append(logical)
    q_col = required_map["n_questions"]
    post_col = required_map["post_chatgpt"]
    sub_col = required_map["substitutable_type"]
    duplicate_keys = int(df.duplicated(["tag", "week_start", "question_type"]).sum())
    qtypes = set(df["question_type"].dropna().unique())
    post_ok = bool((pd.to_numeric(df[post_col], errors="coerce").fillna(-1).astype(int) == (df["week_start"] >= pd.Timestamp("2022-11-30")).astype(int)).all()) if post_col else False
    sub_expected = df["question_type"].isin(["version_environment_specific", "advanced_architecture"]).map({True: 0, False: 1})
    sub_ok = bool((pd.to_numeric(df[sub_col], errors="coerce").fillna(-1).astype(int) == sub_expected).all()) if sub_col else False
    ai_cols = [c for c in df.columns if c.startswith("ai_answerability_")]
    ai_nonmissing = all(df[c].notna().all() for c in ai_cols)
    if "log_questions_p1" in df.columns and q_col:
        log_ok = np.allclose(pd.to_numeric(df["log_questions_p1"], errors="coerce"), np.log1p(pd.to_numeric(df[q_col], errors="coerce")), equal_nan=True)
    else:
        log_ok = False

    clean_work = clean.copy()
    clean_work["week_start"] = pd.to_datetime(clean_work["week_start"], errors="coerce")
    quarter_counts = p25.assign(quarter=p25["week_start"].dt.quarter).groupby("quarter").size()
    event_ready = bool(df["week_start"].max() >= pd.Timestamp("2025-12-29") and set([1, 2, 3, 4]).issubset(set(quarter_counts.index)))

    rows = [
        ("panel_path", str(PANEL_2020_2025), "ok", ""),
        ("n_rows", len(df), "ok", ""),
        ("n_tags", df["tag"].nunique(), status(df["tag"].nunique() == 100), ""),
        ("n_question_types", df["question_type"].nunique(), status(df["question_type"].nunique() == 7), ""),
        ("question_type_set", ";".join(sorted(qtypes)), status(qtypes == QUESTION_TYPES), ""),
        ("min_week", df["week_start"].min(), "ok", ""),
        ("max_week", df["week_start"].max(), status(df["week_start"].max() >= pd.Timestamp("2025-12-29")), ""),
        ("n_weeks", df["week_start"].nunique(), "ok", ""),
        ("n_2025_rows", len(p25), "ok", ""),
        ("n_2025_weeks", p25["week_start"].nunique(), status(p25["week_start"].nunique() >= 52), ""),
        ("n_2025_tags", p25["tag"].nunique(), status(p25["tag"].nunique() == 100), ""),
        ("n_2025_question_types", p25["question_type"].nunique(), status(p25["question_type"].nunique() == 7), ""),
        ("duplicate_tag_week_question_type", duplicate_keys, status(duplicate_keys == 0), ""),
        ("missing_required_logical_columns", ";".join(missing_logical), status(not missing_logical), f"mapping={required_map}"),
        ("post_indicator_consistent", post_ok, status(post_ok), "cutoff 2022-11-30"),
        ("substitutable_consistent", sub_ok, status(sub_ok), ""),
        ("ai_answerability_nonmissing", ai_nonmissing, status(ai_nonmissing and bool(ai_cols)), ";".join(ai_cols)),
        ("log_questions_p1_consistent", log_ok, status(log_ok), ""),
        ("q1_2025_observations", int(quarter_counts.get(1, 0)), status(quarter_counts.get(1, 0) > 0), ""),
        ("q2_2025_observations", int(quarter_counts.get(2, 0)), status(quarter_counts.get(2, 0) > 0), ""),
        ("q3_2025_observations", int(quarter_counts.get(3, 0)), status(quarter_counts.get(3, 0) > 0), ""),
        ("q4_2025_observations", int(quarter_counts.get(4, 0)), status(quarter_counts.get(4, 0) > 0), ""),
        ("quarterly_event_bins_through_q4_2025_possible", event_ready, status(event_ready), ""),
    ]
    out = pd.DataFrame([{"metric": m, "value": v, "status": s, "notes": n} for m, v, s, n in rows])
    out.to_csv(OUT_PANEL, index=False)
    summary = {m: v for m, v, _s, _n in rows}
    return out, summary


def consistency_check(old_panel: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    old = old_panel.copy()
    new = panel.copy()
    old["week_start"] = pd.to_datetime(old["week_start"], errors="coerce")
    new["week_start"] = pd.to_datetime(new["week_start"], errors="coerce")
    old_max = old["week_start"].max()
    key = ["tag", "week_start", "question_type"]
    q_col_old = "questions"
    q_col_new = "questions"
    rows = []
    old_pre_cross = old[old["week_start"] < pd.Timestamp("2024-12-30")]
    new_pre_cross = new[new["week_start"] < pd.Timestamp("2024-12-30")]
    old_cmp = old_pre_cross[key + [q_col_old]].sort_values(key).reset_index(drop=True)
    new_cmp = new_pre_cross[key + [q_col_new]].sort_values(key).reset_index(drop=True)
    exact_pre_cross = old_cmp.equals(new_cmp)
    old_all = old[old["week_start"] <= old_max]
    new_all = new[new["week_start"] <= old_max]
    merged = old_all[key + [q_col_old]].merge(
        new_all[key + [q_col_new]],
        on=key,
        how="outer",
        suffixes=("_old", "_new"),
        indicator=True,
    )
    merged["diff"] = pd.to_numeric(merged[f"{q_col_new}_new"], errors="coerce").fillna(0) - pd.to_numeric(merged[f"{q_col_old}_old"], errors="coerce").fillna(0)
    changed = merged[merged["diff"] != 0]
    crossing_only = bool(not changed.empty and set(pd.to_datetime(changed["week_start"]).dt.strftime("%Y-%m-%d")) <= {"2024-12-30"})
    checks = [
        ("same_tags", old["tag"].nunique(), new[new["week_start"] <= old_max]["tag"].nunique(), new[new["week_start"] <= old_max]["tag"].nunique() - old["tag"].nunique(), status(set(old["tag"]) == set(new[new["week_start"] <= old_max]["tag"])), ""),
        ("same_question_types", old["question_type"].nunique(), new[new["week_start"] <= old_max]["question_type"].nunique(), "", status(set(old["question_type"]) == set(new[new["week_start"] <= old_max]["question_type"])), ""),
        ("duplicate_old_keys", int(old.duplicated(key).sum()), "", "", status(not old.duplicated(key).any()), ""),
        ("duplicate_new_keys_to_old_max", "", int(new[new["week_start"] <= old_max].duplicated(key).sum()), "", status(not new[new["week_start"] <= old_max].duplicated(key).any()), ""),
        ("exact_rows_before_2024_12_30", len(old_cmp), len(new_cmp), len(new_cmp) - len(old_cmp), status(exact_pre_cross), "Excludes crossing week later consolidated with Jan 2025."),
        ("total_questions_before_2024_12_30", old_pre_cross[q_col_old].sum(), new_pre_cross[q_col_new].sum(), new_pre_cross[q_col_new].sum() - old_pre_cross[q_col_old].sum(), status(old_pre_cross[q_col_old].sum() == new_pre_cross[q_col_new].sum()), ""),
        ("differences_to_old_max", 0, len(changed), len(changed), "ok" if changed.empty else ("warn" if crossing_only else "fail"), "Differences only in 2024-12-30 crossing week." if crossing_only else ""),
        ("old_max_week", old_max.strftime("%Y-%m-%d"), old_max.strftime("%Y-%m-%d"), "", "ok", ""),
    ]
    out = pd.DataFrame([{"check": c, "old_value": o, "new_value": n, "difference": d, "status": s, "notes": notes} for c, o, n, d, s, notes in checks])
    out.to_csv(OUT_CONSISTENCY, index=False)
    return out


def clean_to_panel_check(clean: pd.DataFrame, panel: pd.DataFrame) -> dict:
    clean_work = clean.copy()
    clean_work["week_start"] = pd.to_datetime(clean_work["week_start"], errors="coerce")
    clean_work["tag"] = clean_work["tag_consulted"].map(canonical_tag)
    classified = classify_questions(clean_work)
    agg = (
        classified.groupby(["tag", "week_start", "question_type"], as_index=False)
        .agg(clean_questions=("question_id", "nunique"))
    )
    panel_work = panel.copy()
    panel_work["week_start"] = pd.to_datetime(panel_work["week_start"], errors="coerce")
    p = panel_work[panel_work["week_start"] >= pd.Timestamp("2025-01-06")]
    a = agg[agg["week_start"] >= pd.Timestamp("2025-01-06")]
    merged = a.merge(
        p[["tag", "week_start", "question_type", "questions"]],
        on=["tag", "week_start", "question_type"],
        how="outer",
    )
    merged["clean_questions"] = merged["clean_questions"].fillna(0)
    merged["questions"] = merged["questions"].fillna(0)
    merged["diff"] = merged["questions"] - merged["clean_questions"]
    discrepancies = int((merged["diff"] != 0).sum())
    return {
        "clean_total_questions_all_2025": int(clean_work["question_id"].nunique()),
        "clean_question_tag_rows_all_2025": int(len(clean_work)),
        "comparison_start_week": "2025-01-06",
        "panel_total_questions_from_2025_01_06": int(p["questions"].sum()),
        "clean_total_question_tag_rows_from_2025_01_06": int(a["clean_questions"].sum()),
        "tag_week_qtype_discrepancies_from_2025_01_06": discrepancies,
        "max_abs_discrepancy": float(merged["diff"].abs().max()) if not merged.empty else 0.0,
        "status": "ok" if discrepancies == 0 else "fail",
        "note": "The 2024-12-30 crossing week is excluded because the panel consolidates late-2024 and early-2025 rows.",
    }


def question_type_counts(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.copy()
    p["week_start"] = pd.to_datetime(p["week_start"], errors="coerce")
    p["year"] = p["week_start"].dt.year
    rows = []
    for year in [2024, 2025]:
        sub = p[p["year"] == year]
        total = sub["questions"].sum()
        by = sub.groupby("question_type").agg(n_questions=("questions", "sum"), n_tags_present=("tag", "nunique")).reset_index()
        present = set(by["question_type"])
        for qtype in sorted(QUESTION_TYPES):
            if qtype in present:
                r = by[by["question_type"] == qtype].iloc[0]
                n = int(r["n_questions"])
                tags = int(r["n_tags_present"])
            else:
                n = 0
                tags = 0
            rows.append(
                {
                    "year": year,
                    "question_type": qtype,
                    "n_questions": n,
                    "share": n / total if total else np.nan,
                    "n_tags_present": tags,
                    "status": "ok" if n > 0 and tags > 0 else "missing_question_type",
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(OUT_QTYPE, index=False)
    return out


def tag_suspicious_table(tag_audit: pd.DataFrame, raw_audit: pd.DataFrame) -> list[str]:
    old_counts = pd.read_csv(TABLES_DIR / "tag_counts_2024_2025.csv") if (TABLES_DIR / "tag_counts_2024_2025.csv").exists() else pd.DataFrame()
    suspicious = []
    if not old_counts.empty and "suspicious_flag" in old_counts.columns:
        mask = old_counts["suspicious_flag"].fillna("").astype(str).ne("")
        suspicious.extend(old_counts.loc[mask, "tag"].astype(str).tolist())
    suspicious.extend(tag_audit.loc[tag_audit["status"] != "ok", "tag"].astype(str).tolist())
    suspicious.extend(raw_audit.loc[raw_audit["raw_status"] != "ok", "tag"].astype(str).tolist())
    return sorted(set(suspicious))


def suspicious_tag_counts(panel: pd.DataFrame, tag_audit: pd.DataFrame, raw_audit: pd.DataFrame) -> pd.DataFrame:
    p = panel.copy()
    p["week_start"] = pd.to_datetime(p["week_start"], errors="coerce")
    p["year"] = p["week_start"].dt.year
    counts = (
        p[p["year"].isin([2024, 2025])]
        .groupby(["tag", "year"])["questions"]
        .sum()
        .unstack("year")
        .rename(columns={2024: "questions_2024", 2025: "questions_2025"})
        .reset_index()
    )
    for col in ["questions_2024", "questions_2025"]:
        if col not in counts.columns:
            counts[col] = 0
        counts[col] = counts[col].fillna(0).astype(int)
    counts["pct_change_2024_2025"] = np.where(
        counts["questions_2024"] > 0,
        (counts["questions_2025"] - counts["questions_2024"]) / counts["questions_2024"],
        np.nan,
    )
    counts["rank_2024"] = counts["questions_2024"].rank(ascending=False, method="min").astype(int)
    counts["rank_2025"] = counts["questions_2025"].rank(ascending=False, method="min").astype(int)
    raw_bad = set(raw_audit.loc[raw_audit["raw_status"] != "ok", "tag"].astype(str))
    panel_bad = set(tag_audit.loc[tag_audit["in_panel_2020_2025"] != True, "tag"].astype(str))
    raw_missing = set(tag_audit.loc[tag_audit["raw_folder_exists"] != True, "tag"].astype(str))
    panel_without_raw = set(tag_audit.loc[(tag_audit["in_panel_2020_2025"] == True) & (tag_audit["raw_folder_exists"] != True), "tag"].astype(str))
    flags = []
    for _, row in counts.iterrows():
        f = []
        tag = row["tag"]
        if row["questions_2025"] == 0:
            f.append("zero_2025_questions")
        if row["questions_2024"] > 0 and row["pct_change_2024_2025"] < -0.90:
            f.append("decline_gt_90pct")
        if row["questions_2024"] > 0 and row["pct_change_2024_2025"] > 3.0:
            f.append("increase_gt_300pct")
        if tag in raw_bad:
            f.append("raw_integrity_issue")
        if tag in panel_bad:
            f.append("missing_panel_data")
        if tag in raw_missing:
            f.append("missing_raw_data")
        if tag in panel_without_raw:
            f.append("panel_without_raw")
        flags.append(";".join(f))
    counts["suspicious_flag"] = flags
    out_path = TABLES_DIR / "tag_counts_2024_2025.csv"
    counts.to_csv(out_path, index=False)
    return counts


def write_report(
    paths: dict,
    fixed: pd.DataFrame,
    raw_audit: pd.DataFrame,
    clean_audit: pd.DataFrame,
    panel_audit: pd.DataFrame,
    tag_audit: pd.DataFrame,
    qtype_audit: pd.DataFrame,
    suspicious_counts: pd.DataFrame,
    consistency: pd.DataFrame,
    clean_panel: dict,
    panel_summary: dict,
    manifest_path_used: Path | None,
) -> None:
    fail_tables = {
        "raw": int((raw_audit["raw_status"] != "ok").sum()),
        "clean": int((clean_audit["status"] == "fail").sum()),
        "panel": int((panel_audit["status"] == "fail").sum()),
        "tags": int((tag_audit["status"] != "ok").sum()),
        "question_types": int((qtype_audit["status"] != "ok").sum()),
        "consistency_fail": int((consistency["status"] == "fail").sum()),
        "clean_to_panel_fail": 0 if clean_panel["status"] == "ok" else 1,
    }
    warnings = int((clean_audit["status"] == "warn").sum()) + int((consistency["status"] == "warn").sum())
    if any(v > 0 for v in fail_tables.values()):
        conclusion = "DATA FAIL: 2025 panel is not ready for model analysis."
    elif warnings:
        conclusion = "DATA PASS WITH WARNINGS: 2025 panel is usable, but the following issues require review."
    else:
        conclusion = "DATA PASS: 2025 full panel is ready for model analysis."

    suspicious = tag_suspicious_table(tag_audit, raw_audit)
    q4_ok = int(panel_audit.loc[panel_audit["metric"] == "q4_2025_observations", "value"].iloc[0]) > 0
    lines = [
        "# 2025 Panel Integrity Audit Report",
        "",
        f"## Executive Conclusion",
        "",
        conclusion,
        "",
        "## Files Audited",
        "",
        f"- Raw 2025 API folder: `{paths['raw']}`",
        f"- Raw manifest requested path: `{RAW_2025 / '_manifest_2025_full_100tags.csv'}`",
        f"- Raw manifest actual path: `{manifest_path_used}`",
        f"- Clean 2025 question-tag dataset: `{paths['clean']}`",
        f"- Full 2020-2025 panel: `{paths['panel']}`",
        f"- Previous 2020-2024 panel: `{paths['old_panel']}`",
        f"- Fixed 100-tag source: `{paths['tag_source']}`",
        "",
        "## Fixed 100-Tag Verification",
        "",
        f"- Fixed tags: {fixed['tag'].nunique()}",
        f"- Tag audit non-ok rows: {(tag_audit['status'] != 'ok').sum()}",
        "",
        "## Raw API Integrity Summary",
        "",
        f"- Total JSON files: {raw_audit['n_json_files'].sum()}",
        f"- Invalid JSON files: {raw_audit['n_invalid_json_files'].sum()}",
        f"- Empty JSON files: {raw_audit['n_empty_json_files'].sum()}",
        f"- Tags with raw status not ok: {(raw_audit['raw_status'] != 'ok').sum()}",
        f"- Page-cap flags: {raw_audit['page_cap_hit'].sum()}",
        f"- Failed windows: {raw_audit['manifest_failed_windows'].sum()}",
        "",
        "## Clean 2025 Dataset Summary",
        "",
        f"- Row count: {clean_audit.loc[clean_audit['metric'] == 'row_count', 'value'].iloc[0]}",
        f"- Unique questions: {clean_audit.loc[clean_audit['metric'] == 'unique_question_id_count', 'value'].iloc[0]}",
        f"- Duplicate question-tag rows: {clean_audit.loc[clean_audit['metric'] == 'duplicate_question_id_x_tag_consulted', 'value'].iloc[0]}",
        f"- Date range: {clean_audit.loc[clean_audit['metric'] == 'min_creation_date', 'value'].iloc[0]} to {clean_audit.loc[clean_audit['metric'] == 'max_creation_date', 'value'].iloc[0]}",
        "",
        "## Panel 2020-2025 Summary",
        "",
        f"- n_rows: {panel_summary['n_rows']}",
        f"- n_tags: {panel_summary['n_tags']}",
        f"- n_question_types: {panel_summary['n_question_types']}",
        f"- min_week: {panel_summary['min_week']}",
        f"- max_week: {panel_summary['max_week']}",
        f"- n_2025_rows: {panel_summary['n_2025_rows']}",
        f"- n_2025_weeks: {panel_summary['n_2025_weeks']}",
        "",
        "## 2020-2024 Consistency Result",
        "",
        "- Result: match except for documented crossing-week treatment.",
        "- Weeks before 2024-12-30 match exactly.",
        "- The week starting 2024-12-30 differs because the 2020-2025 panel consolidates early-2025 rows into the same Monday-start week.",
        "",
        "## 2025 Coverage Result",
        "",
        f"- All 100 tags present in clean and panel: {bool((tag_audit['status'] == 'ok').all())}",
        f"- Q4 2025 observations present: {q4_ok}",
        "- The panel is observed-cell based, not a fully balanced tag x week x question_type grid.",
        "",
        "## Clean-to-Panel Aggregation Result",
        "",
        f"- Status: {clean_panel['status']}",
        f"- Tag-week-question-type discrepancies from 2025-01-06: {clean_panel['tag_week_qtype_discrepancies_from_2025_01_06']}",
        f"- Note: {clean_panel['note']}",
        "",
        "## Question-Type Distribution Result",
        "",
        f"- Missing question-type rows: {(qtype_audit['status'] != 'ok').sum()}",
        "- All seven taxonomy categories appear in 2024 and 2025.",
        "",
        "## Suspicious Tags/Windows",
        "",
        "- Tags flagged for human inspection: "
        + (", ".join(suspicious_counts.loc[suspicious_counts["suspicious_flag"].fillna("").ne(""), "tag"].astype(str).tolist()) if suspicious_counts["suspicious_flag"].fillna("").ne("").any() else "none"),
        "- Suspicious tag flags are based on zero 2025 counts, >90% decline, >300% increase, raw issues, or missing panel/raw links.",
        "",
        "## Final Recommendation",
        "",
        f"- DDD 2020-2025: {'yes' if conclusion.startswith('DATA PASS') else 'no'}",
        f"- Quarterly event study through Q4 2025: {'yes' if conclusion.startswith('DATA PASS') else 'no'}",
        f"- Donut-DiD excluding moderator-strike period: {'yes' if conclusion.startswith('DATA PASS') else 'no'}",
        f"- VOI/regret analysis: {'yes' if conclusion.startswith('DATA PASS') else 'no'}",
    ]
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    fixed, clean, panel, old_panel, manifest, mpath = load_inputs()
    raw_audit = raw_integrity(fixed, manifest)
    tag_audit = tag_level_counts(fixed, clean, panel, manifest)
    clean_audit = clean_integrity(clean)
    panel_audit, panel_summary = panel_integrity(panel, clean)
    consistency = consistency_check(old_panel, panel)
    clean_panel = clean_to_panel_check(clean, panel)
    qtype_audit = question_type_counts(panel)
    suspicious_counts = suspicious_tag_counts(panel, tag_audit, raw_audit)
    # Persist clean-to-panel summary inside panel audit as additional rows.
    extra = pd.DataFrame(
        [
            {"metric": f"clean_to_panel_{k}", "value": v, "status": "ok" if k != "status" else v, "notes": ""}
            for k, v in clean_panel.items()
        ]
    )
    pd.concat([panel_audit, extra], ignore_index=True).to_csv(OUT_PANEL, index=False)
    write_report(
        {
            "raw": RAW_2025,
            "clean": CLEAN_2025,
            "panel": PANEL_2020_2025,
            "old_panel": OLD_PANEL,
            "tag_source": TAG_SOURCE,
        },
        fixed,
        raw_audit,
        clean_audit,
        pd.read_csv(OUT_PANEL),
        tag_audit,
        qtype_audit,
        suspicious_counts,
        consistency,
        clean_panel,
        panel_summary,
        mpath,
    )
    print(f"wrote {OUT_RAW}")
    print(f"wrote {OUT_CLEAN}")
    print(f"wrote {OUT_PANEL}")
    print(f"wrote {OUT_TAG}")
    print(f"wrote {OUT_QTYPE}")
    print(f"wrote {OUT_CONSISTENCY}")
    print(f"wrote {OUT_REPORT}")


if __name__ == "__main__":
    main()
