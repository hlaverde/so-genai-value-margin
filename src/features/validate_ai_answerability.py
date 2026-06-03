import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.paths import INTERIM_DIR, PROCESSED_DIR, TABLES_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


CODING_COLUMNS = [
    "coder_id",
    "human_ai_answerable",
    "basic_howto_debugging",
    "requires_context",
    "sufficient_information",
    "llm_ai_answerable",
    "notes",
]


def auc_score(y_true: np.ndarray, score: np.ndarray) -> float:
    order = np.argsort(score)
    y = y_true[order]
    n_pos = y.sum()
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return np.nan
    ranks = np.arange(1, len(y) + 1)
    rank_sum_pos = ranks[y == 1].sum()
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def cohen_kappa(a: pd.Series, b: pd.Series) -> float:
    valid = a.notna() & b.notna()
    a = a[valid].astype(int)
    b = b[valid].astype(int)
    if len(a) == 0:
        return np.nan
    po = (a == b).mean()
    pa = a.mean()
    pb = b.mean()
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe == 1:
        return np.nan
    return (po - pe) / (1 - pe)


def fleiss_kappa_binary(matrix: pd.DataFrame) -> float:
    counts = []
    for _, row in matrix.iterrows():
        vals = row.dropna().astype(int)
        if len(vals) < 2:
            continue
        counts.append([int((vals == 0).sum()), int((vals == 1).sum())])
    if not counts:
        return np.nan
    counts = np.asarray(counts, dtype=float)
    n = counts.sum(axis=1)
    if not np.all(n == n[0]):
        # Fleiss assumes equal raters. Use items with modal rater count.
        modal_n = pd.Series(n).mode().iloc[0]
        counts = counts[n == modal_n]
        n = counts.sum(axis=1)
    n_raters = n[0]
    p = counts.sum(axis=0) / counts.sum()
    p_i = ((counts**2).sum(axis=1) - n_raters) / (n_raters * (n_raters - 1))
    p_bar = p_i.mean()
    p_e = (p**2).sum()
    if p_e == 1:
        return np.nan
    return (p_bar - p_e) / (1 - p_e)


def build_sample(pool_path: Path, ai_path: Path, output_path: Path, n_per_stratum: int, seed: int) -> pd.DataFrame:
    pool = read_csv(pool_path)
    ai = read_csv(ai_path)[["tag", "ai_answerability_zscore", "ai_answerability_pca", "ai_answerability_quantile", "ai_answerability_structural"]]
    df = pool.merge(ai, on="tag", how="inner")
    # One question can appear once per tag. Use the highest-answerability tag as the
    # validation exposure for question-level coding.
    df = df.sort_values(["question_id", "ai_answerability_zscore"], ascending=[True, False])
    df = df.drop_duplicates(subset=["question_id"], keep="first")
    df["answerability_stratum"] = pd.qcut(
        df["ai_answerability_zscore"],
        3,
        labels=["low_tag_ai_answerability", "mid_tag_ai_answerability", "high_tag_ai_answerability"],
    )
    sampled_parts = []
    for stratum, group in df.groupby("answerability_stratum", observed=True):
        part = group.sample(min(n_per_stratum, len(group)), random_state=seed).copy()
        part["answerability_stratum"] = str(stratum)
        sampled_parts.append(part)
    sample = pd.concat(sampled_parts, ignore_index=True)
    for col in CODING_COLUMNS:
        sample[col] = ""
    keep_cols = [
        "answerability_stratum",
        "question_id",
        "creation_date",
        "tag",
        "all_tags",
        "title",
        "body",
        "body_length",
        "has_code",
        "short_code",
        "how_to_error_title",
        "answer_count",
        "has_accepted_answer",
        "is_closed",
        "minutes_to_first_answer",
        "ai_answerability_zscore",
        "ai_answerability_pca",
        "ai_answerability_quantile",
        "ai_answerability_structural",
    ] + CODING_COLUMNS
    write_csv(sample[keep_cols], output_path)
    return sample[keep_cols]


def score_validation(coded_path: Path, ai_path: Path, output_path: Path) -> pd.DataFrame:
    coded = read_csv(coded_path)
    ai = read_csv(ai_path)
    for col in ["human_ai_answerable", "llm_ai_answerable", "basic_howto_debugging", "requires_context", "sufficient_information"]:
        coded[col] = pd.to_numeric(coded[col], errors="coerce")

    question = (
        coded.groupby(["question_id", "tag"], as_index=False)
        .agg(
            human_ai_answerable=("human_ai_answerable", "mean"),
            llm_ai_answerable=("llm_ai_answerable", "mean"),
            basic_howto_debugging=("basic_howto_debugging", "mean"),
            requires_context=("requires_context", "mean"),
            sufficient_information=("sufficient_information", "mean"),
            ai_answerability_zscore=("ai_answerability_zscore", "first"),
            ai_answerability_pca=("ai_answerability_pca", "first"),
            ai_answerability_quantile=("ai_answerability_quantile", "first"),
            ai_answerability_structural=("ai_answerability_structural", "first"),
        )
    )
    tag = (
        question.groupby("tag", as_index=False)
        .agg(
            human_ai_answerability_share=("human_ai_answerable", "mean"),
            llm_ai_answerability_share=("llm_ai_answerable", "mean"),
            n_coded_questions=("question_id", "nunique"),
        )
        .merge(ai[["tag", "ai_answerability_zscore", "ai_answerability_pca", "ai_answerability_quantile", "ai_answerability_structural"]], on="tag", how="left")
    )

    coder_matrix = coded.pivot_table(index="question_id", columns="coder_id", values="human_ai_answerable", aggfunc="first")
    kappa = np.nan
    if coder_matrix.shape[1] == 2:
        kappa = cohen_kappa(coder_matrix.iloc[:, 0], coder_matrix.iloc[:, 1])
    elif coder_matrix.shape[1] > 2:
        kappa = fleiss_kappa_binary(coder_matrix)

    q = question.dropna(subset=["human_ai_answerable", "ai_answerability_zscore"]).copy()
    q["human_high_answerability"] = (q["human_ai_answerable"] >= 0.5).astype(int)
    q["llm_high_answerability"] = (q["llm_ai_answerable"] >= 0.5).astype(int)

    rows = [
        {
            "validation_test": "corr_index_vs_human_answerability_share_tag",
            "coefficient": tag["ai_answerability_zscore"].corr(tag["human_ai_answerability_share"]),
            "metric": "pearson_corr",
            "n": tag["human_ai_answerability_share"].notna().sum(),
        },
        {
            "validation_test": "corr_index_vs_llm_answerability_share_tag",
            "coefficient": tag["ai_answerability_zscore"].corr(tag["llm_ai_answerability_share"]),
            "metric": "pearson_corr",
            "n": tag["llm_ai_answerability_share"].notna().sum(),
        },
        {
            "validation_test": "spearman_index_vs_human_answerability_question",
            "coefficient": q["ai_answerability_zscore"].corr(q["human_ai_answerable"], method="spearman"),
            "metric": "spearman_corr",
            "n": len(q),
        },
        {
            "validation_test": "auc_index_predicts_human_high_answerability",
            "coefficient": auc_score(q["human_high_answerability"].to_numpy(), q["ai_answerability_zscore"].to_numpy()),
            "metric": "auc",
            "n": len(q),
        },
        {
            "validation_test": "auc_index_predicts_llm_high_answerability",
            "coefficient": auc_score(q["llm_high_answerability"].to_numpy(), q["ai_answerability_zscore"].to_numpy()),
            "metric": "auc",
            "n": q["llm_high_answerability"].notna().sum(),
        },
        {
            "validation_test": "human_coder_agreement",
            "coefficient": kappa,
            "metric": "cohen_or_fleiss_kappa",
            "n": coder_matrix.dropna(how="all").shape[0],
        },
    ]
    out = pd.DataFrame(rows)
    write_csv(out, output_path)
    write_csv(tag, output_path.with_name(output_path.stem + "_tag_shares.csv"))
    write_csv(question, output_path.with_name(output_path.stem + "_question_scores.csv"))
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and score external validation data for AI answerability.")
    sub = parser.add_subparsers(dest="command", required=True)

    sample = sub.add_parser("build-sample")
    sample.add_argument("--pool", type=Path, default=Path("data/raw/stackoverflow/stackoverflow_question_validation_pool.csv"))
    sample.add_argument("--ai", type=Path, default=PROCESSED_DIR / "ai_answerability_real.csv")
    sample.add_argument("--output", type=Path, default=INTERIM_DIR / "ai_answerability_validation_sample.csv")
    sample.add_argument("--n-per-stratum", type=int, default=750)
    sample.add_argument("--seed", type=int, default=20261130)

    score = sub.add_parser("score")
    score.add_argument("--coded", type=Path, default=INTERIM_DIR / "ai_answerability_validation_sample_coded.csv")
    score.add_argument("--ai", type=Path, default=PROCESSED_DIR / "ai_answerability_real.csv")
    score.add_argument("--output", type=Path, default=TABLES_DIR / "ai_answerability_external_validation.csv")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    if args.command == "build-sample":
        out = build_sample(args.pool, args.ai, args.output, args.n_per_stratum, args.seed)
        logger.info("Wrote validation sample with %s rows to %s", len(out), args.output)
    elif args.command == "score":
        out = score_validation(args.coded, args.ai, args.output)
        logger.info("Wrote validation results to %s", args.output)
        logger.info("\n%s", out.to_string(index=False))


if __name__ == "__main__":
    main()
