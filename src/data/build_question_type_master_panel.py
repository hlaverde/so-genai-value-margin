"""Construye el panel master tag-week-question_type 2020-2024.

Unifica los paneles anuales en una sola tabla con:
    - identificadores: tag, week_start, question_type, substitutable_type
    - outcomes: questions, answers, accepted_answers, avg_score,
                closed_questions, unique_users, body_length_mean,
                code_questions, derived shares
    - tratamiento: post_chatgpt (1 si week_start >= 2022-11-30)
    - moderador: ai_answerability_* (zscore, pca, quantile, structural)
    - utilidades para el modelo: log_questions, log_questions_p1

El cutoff de tratamiento es 2022-11-30 (lanzamiento de ChatGPT).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")
ANSWERABILITY_COLS = [
    "ai_answerability_zscore",
    "ai_answerability_pca",
    "ai_answerability_quantile",
    "ai_answerability_structural",
]


def load_year_panel(year: int, processed_dir: Path) -> pd.DataFrame:
    path = processed_dir / f"stackoverflow_question_type_week_panel_{year}.csv"
    df = pd.read_csv(path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["year"] = year
    return df


def build(
    processed_dir: Path,
    years: list[int],
    output: Path,
    unified_input: Path | None = None,
) -> None:
    if unified_input is not None and unified_input.exists():
        panel = pd.read_csv(unified_input)
        panel["week_start"] = pd.to_datetime(panel["week_start"])
        panel["year"] = panel["week_start"].dt.year
        # Filtra a los años solicitados
        panel = panel[panel["year"].isin(years)].reset_index(drop=True)
    else:
        frames = [load_year_panel(y, processed_dir) for y in years]
        panel = pd.concat(frames, ignore_index=True)
        # Consolida filas que cruzan año (misma semana, distinto archivo anual)
        agg_spec = {
            "questions": "sum",
            "answers": "sum",
            "accepted_answers": "sum",
            "closed_questions": "sum",
            "code_questions": "sum",
            "unique_users": "sum",  # caveat: sobre-cuenta usuarios cross-year
            "avg_score": "mean",
            "body_length_mean": "mean",
        }
        group_cols = ["tag", "week_start", "question_type", "substitutable_type"]
        panel = panel.groupby(group_cols, as_index=False).agg(agg_spec)
        # Recalcula shares
        panel["answer_rate"] = np.where(
            panel["questions"] > 0, panel["answers"] / panel["questions"], np.nan
        )
        panel["accepted_share"] = np.where(
            panel["questions"] > 0, panel["accepted_answers"] / panel["questions"], np.nan
        )
        panel["closed_share"] = np.where(
            panel["questions"] > 0, panel["closed_questions"] / panel["questions"], np.nan
        )
        panel["code_share"] = np.where(
            panel["questions"] > 0, panel["code_questions"] / panel["questions"], np.nan
        )
        panel["year"] = panel["week_start"].dt.year

    # Carga answerability y une por tag
    ans = pd.read_csv(processed_dir / "ai_answerability_real.csv")
    keep_cols = ["tag"] + ANSWERABILITY_COLS + [
        "questions_pre",
        "accepted_answer_rate_pre",
        "short_code_share_pre",
        "how_to_share_pre",
    ]
    ans = ans[keep_cols]
    panel = panel.merge(ans, on="tag", how="left", validate="many_to_one")

    # Indicadores de tratamiento
    panel["post_chatgpt"] = (panel["week_start"] >= CHATGPT_RELEASE).astype(int)
    panel["post_chatgpt_bool"] = panel["week_start"] >= CHATGPT_RELEASE

    # Outcomes utilitarios
    panel["log_questions_p1"] = np.log1p(panel["questions"])
    panel["log_questions"] = np.where(
        panel["questions"] > 0, np.log(panel["questions"]), np.nan
    )
    panel["log_unique_users_p1"] = np.log1p(panel["unique_users"])
    panel["accepted_per_q"] = np.where(
        panel["questions"] > 0, panel["accepted_answers"] / panel["questions"], np.nan
    )

    # Tiempo numérico (semanas desde inicio) — útil para slopes
    min_week = panel["week_start"].min()
    panel["weeks_from_start"] = (
        (panel["week_start"] - min_week).dt.days // 7
    ).astype(int)
    panel["weeks_from_chatgpt"] = (
        (panel["week_start"] - CHATGPT_RELEASE).dt.days // 7
    ).astype(int)

    # IDs categóricos
    panel["tag_qtype"] = panel["tag"] + "::" + panel["question_type"]

    # Validaciones
    expected_keys = panel.duplicated(["tag", "week_start", "question_type"]).sum()
    if expected_keys:
        raise ValueError(f"Duplicates in (tag,week,question_type): {expected_keys}")
    n_tags = panel["tag"].nunique()
    if n_tags != 100:
        raise ValueError(f"Esperaba 100 tags, encontré {n_tags}")

    # Resumen
    print(
        "panel:",
        {
            "rows": len(panel),
            "years": sorted(panel["year"].unique().tolist()),
            "tags": n_tags,
            "weeks": panel["week_start"].nunique(),
            "question_types": panel["question_type"].nunique(),
            "post_share": float(panel["post_chatgpt"].mean()),
            "missing_answerability_rows": int(
                panel["ai_answerability_zscore"].isna().sum()
            ),
        },
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output, index=False)
    print(f"saved -> {output} ({output.stat().st_size:,} bytes)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--processed-dir",
        type=Path,
        default=Path("data/processed"),
    )
    p.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=[2020, 2021, 2022, 2023, 2024],
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/stackoverflow_question_type_master_panel.csv"),
    )
    p.add_argument(
        "--unified-input",
        type=Path,
        default=Path("data/processed/stackoverflow_question_type_week_panel_all.csv"),
        help="Panel ya consolidado (preferido si existe).",
    )
    args = p.parse_args()
    build(args.processed_dir, args.years, args.output, args.unified_input)


if __name__ == "__main__":
    main()
