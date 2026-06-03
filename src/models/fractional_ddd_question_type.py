"""DDD con conteo fraccional de tags.

En el panel principal una pregunta con 3 tags top-100 cuenta como 1
en cada uno de los 3 tags (lo que sobre-cuenta el universo total).
Conteo fraccional: cada pregunta contribuye 1/n_tags_top100 a cada
uno de sus tags. Esto mantiene la suma global = #preguntas únicas.

Procedimiento:
    1. Cargar TODOS los raw (475 archivos) — una fila por (question, tag).
    2. Aplicar alias selenium.
    3. Calcular n_top_tags por pregunta.
    4. Asignar peso w = 1 / n_top_tags.
    5. Clasificar question_type (mismas patrones que prepare_*).
    6. Agregar a panel (tag, week, qtype, sub_type) con questions
       sumando pesos (en vez de conteos).
    7. Merge con answerability, post_chatgpt.
    8. Re-estimar DDD.

Salida:
    data/processed/stackoverflow_question_type_master_panel_fractional.csv
    outputs/tables/fractional_ddd_question_type.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf
import re


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")
TAG_ALIASES = {
    "selenium-webdriver": "selenium",
    "selenium-chromedriver": "selenium",
    "webdriver": "selenium",
    "chromedriver": "selenium",
}

VERSION_ENV_PAT = re.compile(
    r"\b(?:version|environment|windows|linux|mac|ubuntu|install|installed|"
    r"configuration|dependency|package|build error|compiler|runtime)\b",
    flags=re.IGNORECASE,
)
ADVANCED_PAT = re.compile(
    r"\b(?:architecture|design pattern|scalable|performance|optimization|"
    r"microservice|distributed|best practice)\b",
    flags=re.IGNORECASE,
)
DEBUG_PAT = re.compile(
    r"\b(?:error|exception|traceback|not working|bug|debug|failed|failure|"
    r"crash|segmentation fault)\b",
    flags=re.IGNORECASE,
)
HOWTO_PAT = re.compile(
    r"\b(?:how to|how do i|how can i|what is the way|how should i)\b",
    flags=re.IGNORECASE,
)


def load_raw_all(raw_dir: Path) -> pd.DataFrame:
    files = sorted(raw_dir.glob("stackoverflow_question_type_raw_*.csv"))
    # Excluye el archivo legacy
    files = [
        f for f in files
        if f.name != "stackoverflow_question_type_raw_2020_01.csv"
    ]
    print(f"loading {len(files)} raw files...")
    frames = []
    for i, f in enumerate(files):
        if i % 50 == 0:
            print(f"  {i}/{len(files)}")
        frames.append(pd.read_csv(f))
    df = pd.concat(frames, ignore_index=True)
    df["tag"] = df["tag"].replace(TAG_ALIASES)
    df = df.drop_duplicates(["question_id", "tag"]).reset_index(drop=True)
    df["creation_date"] = pd.to_datetime(df["creation_date"], errors="coerce")
    df["week_start"] = pd.to_datetime(df["week_start"], errors="coerce")
    return df


def classify_questions(df: pd.DataFrame) -> pd.DataFrame:
    title = df["title"].fillna("")
    body_length = pd.to_numeric(df["body_length"], errors="coerce").fillna(0)
    has_code = pd.to_numeric(df["has_code"], errors="coerce").fillna(0).astype(int)
    version_env = title.str.contains(VERSION_ENV_PAT, na=False)
    advanced = title.str.contains(ADVANCED_PAT, na=False)
    debugging = title.str.contains(DEBUG_PAT, na=False)
    howto = title.str.contains(HOWTO_PAT, na=False)
    short_code = (has_code == 1) & (body_length <= 1200)
    long_code = (has_code == 1) & (body_length > 1200)
    conditions = [version_env, advanced, debugging, howto, short_code, long_code]
    choices = [
        "version_environment_specific",
        "advanced_architecture",
        "debugging_simple",
        "how_to",
        "short_code",
        "long_code",
    ]
    df = df.copy()
    df["question_type"] = np.select(conditions, choices, default="other_conceptual")
    df["substitutable_type"] = np.where(version_env | advanced, 0, 1)
    return df


def build_fractional_panel(raw: pd.DataFrame) -> pd.DataFrame:
    raw = classify_questions(raw)
    # Pesos fraccionales: 1 / n_top_tags por pregunta
    n_tags_per_q = raw.groupby("question_id").size().rename("n_top_tags")
    raw = raw.merge(n_tags_per_q, left_on="question_id", right_index=True)
    raw["weight"] = 1.0 / raw["n_top_tags"]

    # Outcomes ponderados
    raw["q_weighted"] = raw["weight"]  # contribución fraccional
    raw["answers_weighted"] = raw["weight"] * raw["answer_count"].fillna(0)
    raw["accepted_weighted"] = raw["weight"] * raw["has_accepted_answer"].fillna(0)
    raw["closed_weighted"] = raw["weight"] * raw["is_closed"].fillna(0)

    grouped = (
        raw.groupby(["tag", "week_start", "question_type", "substitutable_type"], dropna=False)
        .agg(
            questions_int=("question_id", "nunique"),
            questions_frac=("q_weighted", "sum"),
            answers_frac=("answers_weighted", "sum"),
            accepted_frac=("accepted_weighted", "sum"),
            closed_frac=("closed_weighted", "sum"),
        )
        .reset_index()
    )
    grouped["log_q_frac_p1"] = np.log1p(grouped["questions_frac"])
    grouped["log_q_int_p1"] = np.log1p(grouped["questions_int"])
    grouped["tag_qtype"] = grouped["tag"] + "::" + grouped["question_type"]
    return grouped


def merge_answerability_post(
    panel: pd.DataFrame, ans_path: Path, ai_cols: list[str]
) -> pd.DataFrame:
    ans = pd.read_csv(ans_path)[["tag"] + ai_cols]
    panel = panel.merge(ans, on="tag", how="left", validate="many_to_one")
    panel["post_chatgpt"] = (panel["week_start"] >= CHATGPT_RELEASE).astype(int)
    return panel


def fit_ddd(df: pd.DataFrame, outcome: str, ai_col: str) -> dict:
    df = df.copy()
    df = df.rename(columns={ai_col: "ai", outcome: "y"})
    df["sub"] = df["substitutable_type"].astype(int)
    df["post"] = df["post_chatgpt"].astype(int)
    df["ai_post"] = df["ai"] * df["post"]
    df["ai_sub"] = df["ai"] * df["sub"]
    df["post_sub"] = df["post"] * df["sub"]
    df["ai_post_sub"] = df["ai"] * df["post"] * df["sub"]
    df["week_id"] = df["week_start"].astype(str)
    formula = (
        "y ~ ai_post + ai_sub + post_sub + ai_post_sub "
        "| tag_qtype + week_id"
    )
    fit = pf.feols(formula, data=df, vcov={"CRV1": "tag"})
    return {
        "ddd": float(fit.coef()["ai_post_sub"]),
        "se": float(fit.se()["ai_post_sub"]),
        "p": float(fit.pvalue()["ai_post_sub"]),
        "n": int(fit._N),
        "outcome": outcome,
    }


def run(raw_dir: Path, ans_path: Path, out_csv: Path, out_panel: Path, ai_col: str) -> None:
    raw = load_raw_all(raw_dir)
    print(f"raw rows: {len(raw):,}, unique questions: {raw['question_id'].nunique():,}")
    panel = build_fractional_panel(raw)
    panel = merge_answerability_post(panel, ans_path, [ai_col])
    out_panel.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(out_panel, index=False)
    print(f"saved fractional panel -> {out_panel} ({len(panel):,} rows)")

    # Comparación: integer baseline vs fractional
    rows = []
    print("\n=== DDD: integer vs fractional ===")
    for outcome in ["log_q_int_p1", "log_q_frac_p1"]:
        r = fit_ddd(panel, outcome, ai_col)
        rows.append(r)
        print(f"  {outcome}: DDD = {r['ddd']:+.4f} (SE {r['se']:.4f}, p={r['p']:.3g}), n={r['n']}")

    out = pd.DataFrame(rows)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)
    print(f"\nsaved {out_csv}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw/stackoverflow"),
    )
    p.add_argument(
        "--answerability-path",
        type=Path,
        default=Path("data/processed/ai_answerability_real.csv"),
    )
    p.add_argument(
        "--out-csv",
        type=Path,
        default=Path("outputs/tables/fractional_ddd_question_type.csv"),
    )
    p.add_argument(
        "--out-panel",
        type=Path,
        default=Path("data/processed/stackoverflow_question_type_master_panel_fractional.csv"),
    )
    p.add_argument("--answerability", default="ai_answerability_zscore")
    args = p.parse_args()
    run(args.raw_dir, args.answerability_path, args.out_csv, args.out_panel, args.answerability)


if __name__ == "__main__":
    main()
