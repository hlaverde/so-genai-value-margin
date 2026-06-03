import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

from src.config import CHATGPT_RELEASE_DATE
from src.paths import PROCESSED_DIR, TABLES_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


def load_data(user_path: Path, ai_path: Path) -> pd.DataFrame:
    users = read_csv(user_path)
    ai = read_csv(ai_path)[["tag", "ai_answerability_zscore"]]
    df = users.merge(ai, on="tag", how="left")
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["post_chatgpt"] = df["week_start"] >= pd.Timestamp(CHATGPT_RELEASE_DATE)
    df["group_id"] = (
        df["tag"].astype(str)
        + "_new"
        + df["new_user"].astype(str)
        + "_lowrep"
        + df["low_reputation_user"].astype(str)
    )
    for col in ["posts", "questions", "answers", "unique_users"]:
        df[f"log_{col}"] = np.log1p(df[col])
    return df.sort_values(["group_id", "week_start"])


def descriptives(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.assign(period=np.where(df["post_chatgpt"], "post", "pre"))
        .groupby(["period", "new_user", "low_reputation_user"], as_index=False)
        .agg(
            tag_group_weeks=("tag", "size"),
            posts=("posts", "sum"),
            questions=("questions", "sum"),
            answers=("answers", "sum"),
            unique_users=("unique_users", "sum"),
        )
    )


def estimate_group_heterogeneity(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    data = df.copy()
    data["ai_x_post"] = data["ai_answerability_zscore"] * data["post_chatgpt"].astype(int)
    data["ai_x_post_x_new"] = data["ai_x_post"] * data["new_user"]
    data["ai_x_post_x_lowrep"] = data["ai_x_post"] * data["low_reputation_user"]
    panel = data.set_index(["group_id", "week_start"])
    exog = ["ai_x_post", "ai_x_post_x_new", "ai_x_post_x_lowrep"]
    for outcome in ["log_posts", "log_questions", "log_answers", "log_unique_users"]:
        model_data = panel[[outcome] + exog].dropna()
        res = PanelOLS(
            model_data[outcome],
            model_data[exog],
            entity_effects=True,
            time_effects=True,
        ).fit(cov_type="clustered", cluster_entity=True)
        for term in exog:
            rows.append(
                {
                    "outcome": outcome,
                    "term": term,
                    "estimate": res.params[term],
                    "std_error": res.std_errors[term],
                    "t_stat": res.tstats[term],
                    "p_value": res.pvalues[term],
                    "n_obs": int(res.nobs),
                    "r2_within": res.rsquared_within,
                }
            )
    return pd.DataFrame(rows)


def run(user_path: Path, ai_path: Path, tables_dir: Path) -> dict[str, Path]:
    df = load_data(user_path, ai_path)
    desc = descriptives(df)
    het = estimate_group_heterogeneity(df)
    outputs = {
        "descriptives": tables_dir / "stackoverflow_user_group_descriptives_real.csv",
        "heterogeneity": tables_dir / "stackoverflow_user_group_heterogeneity_real.csv",
    }
    write_csv(desc, outputs["descriptives"])
    write_csv(het, outputs["heterogeneity"])
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run first-pass Stack Overflow user-group heterogeneity models.")
    parser.add_argument("--user-groups", type=Path, default=PROCESSED_DIR / "stackoverflow_user_group_tag_week_real.csv")
    parser.add_argument("--ai-answerability", type=Path, default=PROCESSED_DIR / "ai_answerability_real.csv")
    parser.add_argument("--tables-dir", type=Path, default=TABLES_DIR)
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    outputs = run(args.user_groups, args.ai_answerability, args.tables_dir)
    for key, path in outputs.items():
        logger.info("Wrote %s to %s", key, path)


if __name__ == "__main__":
    main()
