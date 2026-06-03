import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

from src.config import CHATGPT_RELEASE_DATE
from src.paths import PROCESSED_DIR, TABLES_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


AI_ML_TAGS = {
    "artificial-intelligence",
    "machine-learning",
    "deep-learning",
    "tensorflow",
    "pytorch",
    "keras",
    "scikit-learn",
    "nlp",
    "neural-network",
}


def prepare(path: Path) -> pd.DataFrame:
    df = read_csv(path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["log_questions"] = np.log1p(df["questions"])
    df["log_answers"] = np.log1p(df["answers"])
    return df


def did(df: pd.DataFrame, outcome: str, post_date: pd.Timestamp, sample: str) -> dict[str, object]:
    data = df.copy()
    data["post"] = data["week_start"] >= post_date
    data["ai_x_post"] = data["ai_answerability_zscore"] * data["post"].astype(int)
    panel = data.set_index(["tag", "week_start"])
    res = PanelOLS(
        panel[outcome],
        panel[["ai_x_post"]],
        entity_effects=True,
        time_effects=True,
    ).fit(cov_type="clustered", cluster_entity=True)
    return {
        "sample": sample,
        "outcome": outcome,
        "post_date": post_date.date().isoformat(),
        "estimate": res.params["ai_x_post"],
        "std_error": res.std_errors["ai_x_post"],
        "t_stat": res.tstats["ai_x_post"],
        "p_value": res.pvalues["ai_x_post"],
        "n_obs": int(res.nobs),
    }


def run(input_path: Path, output: Path) -> pd.DataFrame:
    df = prepare(input_path)
    rows = []
    samples = {
        "baseline": df,
        "exclude_ai_ml_tags": df[~df["tag"].isin(AI_ML_TAGS)].copy(),
        "no_transition_8_weeks": df[
            (df["week_start"] < pd.Timestamp(CHATGPT_RELEASE_DATE) - pd.Timedelta(weeks=8))
            | (df["week_start"] > pd.Timestamp(CHATGPT_RELEASE_DATE) + pd.Timedelta(weeks=8))
        ].copy(),
    }
    for sample_name, sample_df in samples.items():
        for outcome in ["log_questions", "log_answers", "code_share", "short_code_share"]:
            rows.append(did(sample_df, outcome, pd.Timestamp(CHATGPT_RELEASE_DATE), sample_name))

    for outcome in ["log_questions", "log_answers", "code_share", "short_code_share"]:
        rows.append(did(df[df["week_start"] < pd.Timestamp(CHATGPT_RELEASE_DATE)].copy(), outcome, pd.Timestamp("2021-11-30"), "placebo_2021_pre_period_only"))

    out = pd.DataFrame(rows)
    write_csv(out, output)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run first-pass robustness checks for real Stack Overflow DID.")
    parser.add_argument("--input", type=Path, default=PROCESSED_DIR / "stackoverflow_tag_week_panel_real.csv")
    parser.add_argument("--output", type=Path, default=TABLES_DIR / "stackoverflow_robustness_real.csv")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    out = run(args.input, args.output)
    logger.info("Wrote robustness table to %s", args.output)
    logger.info("\n%s", out.to_string(index=False))


if __name__ == "__main__":
    main()
