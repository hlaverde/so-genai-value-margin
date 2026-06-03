import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from src.config import CHATGPT_RELEASE_DATE
from src.paths import INTERIM_DIR, PROCESSED_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger
from src.utils.validation import require_columns


STRUCTURAL_COMPONENTS = [
    "accepted_answer_rate_pre",
    "answer_rate_pre",
    "historical_frequency_pre",
    "tag_maturity_weeks_pre",
]

ALL_COMPONENTS = STRUCTURAL_COMPONENTS + [
    "short_code_share_pre",
    "how_to_share_pre",
]


def _safe_zscores(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for col in columns:
        values = pd.to_numeric(df[col], errors="coerce").fillna(0)
        std = values.std(ddof=0)
        out[col] = 0.0 if std == 0 else (values - values.mean()) / std
    return out


def _scaled_average(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    z = _safe_zscores(df, columns)
    return z.mean(axis=1)


def _pca_score(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    if len(df) < 2:
        return pd.Series(np.zeros(len(df)), index=df.index)
    values = df[columns].apply(pd.to_numeric, errors="coerce").fillna(0)
    if values.nunique().sum() <= len(columns):
        return pd.Series(np.zeros(len(df)), index=df.index)
    scaled = StandardScaler().fit_transform(values)
    scores = PCA(n_components=1).fit_transform(scaled).ravel()
    return pd.Series(scores, index=df.index)


def _quantile_rank(series: pd.Series, n_quantiles: int = 5) -> pd.Series:
    ranked = series.rank(method="average")
    bins = min(n_quantiles, ranked.nunique())
    if bins <= 1:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return pd.qcut(ranked, q=bins, labels=False, duplicates="drop") / (bins - 1)


def build_ai_answerability(tag_week: pd.DataFrame, post_complexity: pd.DataFrame) -> pd.DataFrame:
    require_columns(
        tag_week,
        ["tag", "week_start", "questions", "accepted_answers", "answer_rate"],
        "tag_week_clean",
    )
    require_columns(
        post_complexity,
        ["tag", "creation_date", "short_code_question", "how_to_question"],
        "post_complexity_features",
    )

    tw = tag_week.copy()
    tw["week_start"] = pd.to_datetime(tw["week_start"])
    tw_pre = tw[tw["week_start"] < pd.Timestamp(CHATGPT_RELEASE_DATE)].copy()
    tw_pre["active_week"] = tw_pre["questions"] > 0

    tag_stats = (
        tw_pre.groupby("tag", as_index=False)
        .agg(
            questions_pre=("questions", "sum"),
            accepted_answers_pre=("accepted_answers", "sum"),
            answer_rate_pre=("answer_rate", "mean"),
            historical_frequency_pre=("questions", "sum"),
            tag_maturity_weeks_pre=("active_week", "sum"),
        )
    )
    tag_stats["accepted_answer_rate_pre"] = (
        tag_stats["accepted_answers_pre"] / tag_stats["questions_pre"].replace({0: np.nan})
    ).fillna(0)

    pc = post_complexity.copy()
    pc["creation_date"] = pd.to_datetime(pc["creation_date"])
    pc_pre = pc[pc["creation_date"] < pd.Timestamp(CHATGPT_RELEASE_DATE)].copy()
    post_stats = (
        pc_pre.groupby("tag", as_index=False)
        .agg(
            short_code_share_pre=("short_code_question", "mean"),
            how_to_share_pre=("how_to_question", "mean"),
        )
    )

    out = tag_stats.merge(post_stats, on="tag", how="left").fillna(0)
    out["ai_answerability_zscore"] = _scaled_average(out, ALL_COMPONENTS)
    out["ai_answerability_pca"] = _pca_score(out, ALL_COMPONENTS)
    out["ai_answerability_quantile"] = _quantile_rank(out["ai_answerability_zscore"])
    out["ai_answerability_structural"] = _scaled_average(out, STRUCTURAL_COMPONENTS)
    return out.sort_values("tag")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build pre-ChatGPT tag-level AI answerability indices.")
    parser.add_argument("--tag-week", type=Path, default=INTERIM_DIR / "stackoverflow" / "tag_week_clean.csv")
    parser.add_argument("--post-complexity", type=Path, default=PROCESSED_DIR / "post_complexity_features.csv")
    parser.add_argument("--output", type=Path, default=PROCESSED_DIR / "ai_answerability.csv")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    out = build_ai_answerability(read_csv(args.tag_week), read_csv(args.post_complexity))
    write_csv(out, args.output)
    logger.info("Wrote AI answerability indices to %s", args.output)


if __name__ == "__main__":
    main()
