import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

from src.paths import PROCESSED_DIR, TABLES_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


def auc_score(y_true: np.ndarray, score: np.ndarray) -> float:
    valid = ~np.isnan(y_true) & ~np.isnan(score)
    y_true = y_true[valid].astype(int)
    score = score[valid]
    order = np.argsort(score)
    y = y_true[order]
    n_pos = y.sum()
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return np.nan
    ranks = np.arange(1, len(y) + 1)
    rank_sum_pos = ranks[y == 1].sum()
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if std == 0 or pd.isna(std):
        return series * 0
    return (series - series.mean()) / std


def prepare_question_pool(pool_path: Path, ai_path: Path) -> pd.DataFrame:
    pool = read_csv(pool_path)
    ai = read_csv(ai_path)[
        [
            "tag",
            "ai_answerability_zscore",
            "ai_answerability_pca",
            "ai_answerability_quantile",
            "ai_answerability_structural",
        ]
    ]
    df = pool.merge(ai, on="tag", how="inner")
    # One question may appear under several top tags. For question-level validation,
    # keep the highest-AI tag exposure to avoid repeated identical text.
    df = df.sort_values(["question_id", "ai_answerability_zscore"], ascending=[True, False])
    df = df.drop_duplicates(subset=["question_id"], keep="first").copy()

    minutes = pd.to_numeric(df["minutes_to_first_answer"], errors="coerce")
    df["answered"] = (pd.to_numeric(df["answer_count"], errors="coerce").fillna(0) > 0).astype(int)
    df["accepted"] = pd.to_numeric(df["has_accepted_answer"], errors="coerce").fillna(0).astype(int)
    df["not_closed"] = (1 - pd.to_numeric(df["is_closed"], errors="coerce").fillna(0)).astype(int)
    df["fast_answer_24h"] = ((minutes <= 24 * 60) & minutes.notna()).astype(int)
    df["fast_answer_6h"] = ((minutes <= 6 * 60) & minutes.notna()).astype(int)
    df["accepted_fast_24h"] = ((df["accepted"] == 1) & (minutes <= 24 * 60) & minutes.notna()).astype(int)
    df["answered_not_closed"] = ((df["answered"] == 1) & (df["not_closed"] == 1)).astype(int)
    df["accepted_not_closed"] = ((df["accepted"] == 1) & (df["not_closed"] == 1)).astype(int)
    df["short_code_binary"] = pd.to_numeric(df["short_code"], errors="coerce").fillna(0).astype(int)
    df["howto_binary"] = pd.to_numeric(df["how_to_error_title"], errors="coerce").fillna(0).astype(int)

    # Revealed answerability is intentionally built from pre-ChatGPT observed
    # community resolution signals, not from post-treatment outcomes.
    inv_minutes = -np.log1p(minutes.clip(lower=0))
    components = pd.DataFrame(
        {
            "accepted": df["accepted"],
            "answered_not_closed": df["answered_not_closed"],
            "accepted_fast_24h": df["accepted_fast_24h"],
            "fast_answer_24h": df["fast_answer_24h"],
            "inverse_log_minutes": inv_minutes.fillna(inv_minutes.min()),
        }
    )
    df["revealed_answerability_score"] = components.apply(zscore).mean(axis=1)
    threshold = df["revealed_answerability_score"].quantile(0.67)
    df["revealed_high_answerability"] = (df["revealed_answerability_score"] >= threshold).astype(int)
    return df


def tag_validation(df: pd.DataFrame) -> pd.DataFrame:
    tag = (
        df.groupby("tag", as_index=False)
        .agg(
            n_questions=("question_id", "nunique"),
            revealed_answerability_mean=("revealed_answerability_score", "mean"),
            revealed_high_share=("revealed_high_answerability", "mean"),
            accepted_share=("accepted", "mean"),
            fast_answer_24h_share=("fast_answer_24h", "mean"),
            accepted_fast_24h_share=("accepted_fast_24h", "mean"),
            answered_not_closed_share=("answered_not_closed", "mean"),
            short_code_share_validation=("short_code_binary", "mean"),
            howto_share_validation=("howto_binary", "mean"),
            ai_answerability_zscore=("ai_answerability_zscore", "first"),
            ai_answerability_pca=("ai_answerability_pca", "first"),
            ai_answerability_quantile=("ai_answerability_quantile", "first"),
            ai_answerability_structural=("ai_answerability_structural", "first"),
        )
    )
    return tag


def validation_metrics(question: pd.DataFrame, tag: pd.DataFrame) -> pd.DataFrame:
    rows = []
    tests = [
        ("tag_corr_revealed_mean", tag, "ai_answerability_zscore", "revealed_answerability_mean", "pearson"),
        ("tag_spearman_revealed_mean", tag, "ai_answerability_zscore", "revealed_answerability_mean", "spearman"),
        ("tag_corr_revealed_high_share", tag, "ai_answerability_zscore", "revealed_high_share", "pearson"),
        ("tag_corr_fast_answer_24h_share", tag, "ai_answerability_zscore", "fast_answer_24h_share", "pearson"),
        ("tag_corr_accepted_fast_24h_share", tag, "ai_answerability_zscore", "accepted_fast_24h_share", "pearson"),
        ("tag_corr_answered_not_closed_share", tag, "ai_answerability_zscore", "answered_not_closed_share", "pearson"),
        ("question_spearman_revealed_score", question, "ai_answerability_zscore", "revealed_answerability_score", "spearman"),
    ]
    for name, data, x, y, method in tests:
        rows.append(
            {
                "validation_test": name,
                "metric": f"{method}_correlation",
                "coefficient": data[x].corr(data[y], method=method),
                "n": data[[x, y]].dropna().shape[0],
                "interpretation": "higher current index aligns with observed pre-ChatGPT answerability" if name.startswith("tag") else "question-level rank validation",
            }
        )
    rows.append(
        {
            "validation_test": "auc_index_predicts_revealed_high_question",
            "metric": "auc",
            "coefficient": auc_score(
                question["revealed_high_answerability"].to_numpy(float),
                question["ai_answerability_zscore"].to_numpy(float),
            ),
            "n": int(question[["revealed_high_answerability", "ai_answerability_zscore"]].dropna().shape[0]),
            "interpretation": "AUC for current index predicting high revealed answerability",
        }
    )
    return pd.DataFrame(rows)


def write_latex(metrics: pd.DataFrame, output_tex: Path) -> None:
    labels = {
        "tag_corr_revealed_mean": "Tag-level revealed score, Pearson",
        "tag_spearman_revealed_mean": "Tag-level revealed score, Spearman",
        "tag_corr_revealed_high_share": "Tag-level high-answerability share",
        "tag_corr_fast_answer_24h_share": "Fast answer within 24h share",
        "tag_corr_accepted_fast_24h_share": "Accepted fast answer within 24h share",
        "tag_corr_answered_not_closed_share": "Answered and not closed share",
        "question_spearman_revealed_score": "Question-level revealed score, Spearman",
        "auc_index_predicts_revealed_high_question": "AUC predicting high revealed answerability",
    }
    lines = [
        r"\begin{table}[ht]",
        r"\centering",
        r"\caption{Revealed-answerability validation of the AI-answerability proxy. "
        r"The validation outcome is built only from pre-ChatGPT Stack Overflow "
        r"resolution signals: accepted answers, answered-and-not-closed status, "
        r"fast first answer, and accepted fast answer. Positive values indicate "
        r"that tags with higher AI-answerability also had objectively more "
        r"resolvable pre-treatment questions.}",
        r"\label{tab:revealed_answerability_validation}",
        r"\small",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Validation outcome & Metric & Coef. & $N$ \\",
        r"\midrule",
    ]
    for _, row in metrics.iterrows():
        metric = "AUC" if row["metric"] == "auc" else row["metric"].replace("_correlation", "")
        lines.append(
            f"{labels.get(row['validation_test'], row['validation_test'])} & "
            f"{metric} & {float(row['coefficient']):.3f} & "
            f"{int(row['n']):,} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    output_tex.parent.mkdir(parents=True, exist_ok=True)
    output_tex.write_text("\n".join(lines), encoding="utf-8")


def run(
    pool_path: Path,
    ai_path: Path,
    output_metrics: Path,
    output_tag: Path,
    output_question: Path,
    output_tex: Path | None = None,
) -> dict[str, Path]:
    question = prepare_question_pool(pool_path, ai_path)
    tag = tag_validation(question)
    metrics = validation_metrics(question, tag)
    write_csv(metrics, output_metrics)
    write_csv(tag, output_tag)
    write_csv(question, output_question)
    outputs = {"metrics": output_metrics, "tag": output_tag, "question": output_question}
    if output_tex is not None:
        write_latex(metrics, output_tex)
        outputs["tex"] = output_tex
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Objective revealed-answerability validation for the AI-answerability index.")
    parser.add_argument("--pool", type=Path, default=Path("data/raw/stackoverflow/stackoverflow_question_validation_pool.csv"))
    parser.add_argument("--ai", type=Path, default=PROCESSED_DIR / "ai_answerability_real.csv")
    parser.add_argument("--output-metrics", type=Path, default=TABLES_DIR / "ai_answerability_revealed_validation.csv")
    parser.add_argument("--output-tag", type=Path, default=PROCESSED_DIR / "ai_answerability_revealed_validation_tag.csv")
    parser.add_argument("--output-question", type=Path, default=PROCESSED_DIR / "ai_answerability_revealed_validation_question.csv")
    parser.add_argument("--output-tex", type=Path, default=TABLES_DIR / "table_revealed_answerability_validation.tex")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    outputs = run(args.pool, args.ai, args.output_metrics, args.output_tag, args.output_question, args.output_tex)
    for key, path in outputs.items():
        logger.info("Wrote %s to %s", key, path)
    metrics = read_csv(args.output_metrics)
    logger.info("\n%s", metrics.to_string(index=False))


if __name__ == "__main__":
    main()
