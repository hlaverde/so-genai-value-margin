import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from linearmodels.panel import PanelOLS

from src.config import CHATGPT_RELEASE_DATE
from src.paths import PROCESSED_DIR, TABLES_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


OUTCOMES = ["log_questions", "log_answers", "code_share", "short_code_share"]
AI_INDICES = [
    "ai_answerability_zscore",
    "ai_answerability_pca",
    "ai_answerability_quantile",
    "ai_answerability_structural",
]


def load_panel(path: Path) -> pd.DataFrame:
    df = read_csv(path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["post_chatgpt"] = df["week_start"] >= pd.Timestamp(CHATGPT_RELEASE_DATE)
    df["log_questions"] = np.log1p(df["questions"])
    df["log_answers"] = np.log1p(df["answers"])
    min_week = df["week_start"].min()
    df["week_index"] = ((df["week_start"] - min_week).dt.days // 7).astype(int)
    return df.sort_values(["tag", "week_start"])


def pretrend_slopes(df: pd.DataFrame) -> pd.DataFrame:
    pre = df[df["week_start"] < pd.Timestamp(CHATGPT_RELEASE_DATE)].copy()
    rows = []
    for tag, g in pre.groupby("tag"):
        if len(g) < 10:
            continue
        for outcome in ["log_questions", "log_answers", "code_share", "short_code_share"]:
            fit = smf.ols(f"{outcome} ~ week_index", data=g).fit()
            rows.append(
                {
                    "tag": tag,
                    "outcome": outcome,
                    "pretrend_slope": fit.params["week_index"],
                    "pretrend_p_value": fit.pvalues["week_index"],
                    "n_weeks": len(g),
                    "ai_answerability_zscore": g["ai_answerability_zscore"].iloc[0],
                }
            )
    out = pd.DataFrame(rows)
    corr_rows = []
    for outcome, g in out.groupby("outcome"):
        corr = g["pretrend_slope"].corr(g["ai_answerability_zscore"])
        corr_rows.append({"outcome": outcome, "corr_pretrend_slope_ai": corr, "n_tags": len(g)})
    return out, pd.DataFrame(corr_rows)


def did_panel(df: pd.DataFrame, outcome: str, ai_index: str, sample_name: str) -> dict[str, object]:
    data = df.copy()
    data["ai_x_post"] = data[ai_index] * data["post_chatgpt"].astype(int)
    panel = data.set_index(["tag", "week_start"])
    res = PanelOLS(
        panel[outcome],
        panel[["ai_x_post"]],
        entity_effects=True,
        time_effects=True,
    ).fit(cov_type="clustered", cluster_entity=True)
    return {
        "model": "tag_fe_week_fe",
        "sample": sample_name,
        "outcome": outcome,
        "ai_index": ai_index,
        "estimate": res.params["ai_x_post"],
        "std_error": res.std_errors["ai_x_post"],
        "t_stat": res.tstats["ai_x_post"],
        "p_value": res.pvalues["ai_x_post"],
        "n_obs": int(res.nobs),
    }


def did_with_tag_trends(df: pd.DataFrame, outcome: str, ai_index: str, sample_name: str) -> dict[str, object]:
    data = df.copy()
    data["ai_x_post"] = data[ai_index] * data["post_chatgpt"].astype(int)
    # C(tag):week_index adds tag-specific linear trends while C(tag) and C(week_start)
    # absorb tag and week shocks.
    formula = f"{outcome} ~ ai_x_post + C(tag) + C(week_start) + C(tag):week_index"
    res = smf.ols(formula, data=data).fit(cov_type="cluster", cov_kwds={"groups": data["tag"]})
    return {
        "model": "tag_fe_week_fe_tag_linear_trends",
        "sample": sample_name,
        "outcome": outcome,
        "ai_index": ai_index,
        "estimate": res.params["ai_x_post"],
        "std_error": res.bse["ai_x_post"],
        "t_stat": res.tvalues["ai_x_post"],
        "p_value": res.pvalues["ai_x_post"],
        "n_obs": int(res.nobs),
    }


def build_samples(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    tag_totals = df.groupby("tag")["questions"].sum().sort_values(ascending=False)
    top5 = set(tag_totals.head(5).index)
    return {
        "baseline": df,
        "exclude_top5_tags": df[~df["tag"].isin(top5)].copy(),
        "balanced_2020_2024": df[(df["week_start"] >= "2020-01-01") & (df["week_start"] < "2025-01-01")].copy(),
        "drop_transition_8w": df[
            (df["week_start"] < pd.Timestamp(CHATGPT_RELEASE_DATE) - pd.Timedelta(weeks=8))
            | (df["week_start"] > pd.Timestamp(CHATGPT_RELEASE_DATE) + pd.Timedelta(weeks=8))
        ].copy(),
    }


def robustness_grid(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    samples = build_samples(df)
    for sample_name, sample_df in samples.items():
        for outcome in OUTCOMES:
            for ai_index in AI_INDICES:
                rows.append(did_panel(sample_df, outcome, ai_index, sample_name))
                rows.append(did_with_tag_trends(sample_df, outcome, ai_index, sample_name))
    return pd.DataFrame(rows)


def run(input_path: Path, tables_dir: Path) -> dict[str, Path]:
    df = load_panel(input_path)
    slopes, corr = pretrend_slopes(df)
    robust = robustness_grid(df)
    outputs = {
        "pretrend_slopes": tables_dir / "stackoverflow_pretrend_slopes_real.csv",
        "pretrend_corr": tables_dir / "stackoverflow_pretrend_ai_correlation_real.csv",
        "identification_grid": tables_dir / "stackoverflow_identification_grid_real.csv",
    }
    write_csv(slopes, outputs["pretrend_slopes"])
    write_csv(corr, outputs["pretrend_corr"])
    write_csv(robust, outputs["identification_grid"])
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strengthen Stack Overflow identification checks.")
    parser.add_argument("--input", type=Path, default=PROCESSED_DIR / "stackoverflow_tag_week_panel_real.csv")
    parser.add_argument("--tables-dir", type=Path, default=TABLES_DIR)
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    outputs = run(args.input, args.tables_dir)
    for key, path in outputs.items():
        logger.info("Wrote %s to %s", key, path)


if __name__ == "__main__":
    main()
