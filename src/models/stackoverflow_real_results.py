import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

from src.config import CHATGPT_RELEASE_DATE
from src.paths import FIGURES_DIR, PROCESSED_DIR, TABLES_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


OUTCOMES = {
    "log_questions": "log(1 + questions)",
    "log_answers": "log(1 + answers)",
    "answer_rate": "answer rate",
    "accepted_answer_share": "accepted answer share",
    "avg_body_length": "average body length",
    "code_share": "code share",
    "how_to_share": "how-to/error title share",
    "short_code_share": "short code share",
}


def load_panel(path: Path) -> pd.DataFrame:
    df = read_csv(path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["post_chatgpt"] = df["week_start"] >= pd.Timestamp(CHATGPT_RELEASE_DATE)
    df["log_questions"] = np.log1p(df["questions"])
    df["log_answers"] = np.log1p(df["answers"])
    df["log_unique_users"] = np.log1p(df["unique_users"])
    return df.sort_values(["tag", "week_start"])


def descriptive_tables(df: pd.DataFrame, output_dir: Path) -> dict[str, Path]:
    prepost = (
        df.assign(period=np.where(df["post_chatgpt"], "post", "pre"))
        .groupby("period", as_index=False)
        .agg(
            weeks=("week_start", "nunique"),
            tag_weeks=("tag", "size"),
            questions=("questions", "sum"),
            answers=("answers", "sum"),
            unique_users=("unique_users", "sum"),
            mean_answer_rate=("answer_rate", "mean"),
            mean_body_length=("avg_body_length", "mean"),
            mean_code_share=("code_share", "mean"),
        )
    )

    quantile = (
        df.assign(ai_quantile=pd.qcut(df["ai_answerability_zscore"], 4, labels=["Q1 low", "Q2", "Q3", "Q4 high"]))
        .groupby(["ai_quantile", "post_chatgpt"], observed=False, as_index=False)
        .agg(
            questions=("questions", "sum"),
            answers=("answers", "sum"),
            tag_weeks=("tag", "size"),
            mean_answer_rate=("answer_rate", "mean"),
            mean_body_length=("avg_body_length", "mean"),
        )
    )

    ai_top_bottom = (
        df[["tag", "ai_answerability_zscore", "ai_answerability_structural", "ai_answerability_pca"]]
        .drop_duplicates()
        .sort_values("ai_answerability_zscore", ascending=False)
    )
    ai_top_bottom = pd.concat([ai_top_bottom.head(15), ai_top_bottom.tail(15)])

    outputs = {
        "prepost": output_dir / "stackoverflow_prepost_descriptives.csv",
        "quantile": output_dir / "stackoverflow_ai_quantile_descriptives.csv",
        "ai_tags": output_dir / "stackoverflow_ai_answerability_top_bottom.csv",
    }
    write_csv(prepost, outputs["prepost"])
    write_csv(quantile, outputs["quantile"])
    write_csv(ai_top_bottom, outputs["ai_tags"])
    return outputs


def estimate_did(df: pd.DataFrame, treatment: str = "ai_answerability_zscore") -> pd.DataFrame:
    rows = []
    data = df.copy()
    data["ai_x_post"] = data[treatment] * data["post_chatgpt"].astype(int)
    data = data.set_index(["tag", "week_start"])

    for outcome, label in OUTCOMES.items():
        model_data = data[[outcome, "ai_x_post"]].dropna()
        res = PanelOLS(
            model_data[outcome],
            model_data[["ai_x_post"]],
            entity_effects=True,
            time_effects=True,
        ).fit(cov_type="clustered", cluster_entity=True)
        rows.append(
            {
                "outcome": outcome,
                "label": label,
                "term": "AI_Answerability x PostChatGPT",
                "estimate": res.params["ai_x_post"],
                "std_error": res.std_errors["ai_x_post"],
                "t_stat": res.tstats["ai_x_post"],
                "p_value": res.pvalues["ai_x_post"],
                "n_obs": int(res.nobs),
                "r2_within": res.rsquared_within,
            }
        )
    return pd.DataFrame(rows)


def estimate_event_study(
    df: pd.DataFrame,
    outcome: str = "log_questions",
    treatment: str = "ai_answerability_zscore",
    window: int = 104,
    bin_width: int = 4,
) -> pd.DataFrame:
    data = df.copy()
    event_week = pd.Timestamp("2022-11-28")
    data["relative_week"] = ((data["week_start"] - event_week).dt.days // 7).astype(int)
    data = data[(data["relative_week"] >= -window) & (data["relative_week"] <= window)].copy()
    data["event_bin"] = (np.floor(data["relative_week"] / bin_width) * bin_width).astype(int)
    omitted = -bin_width
    bins = sorted(b for b in data["event_bin"].unique() if b != omitted)
    for b in bins:
        name = f"event_{b:+d}".replace("+", "p").replace("-", "m")
        data[name] = data[treatment] * (data["event_bin"] == b).astype(int)

    exog_cols = [f"event_{b:+d}".replace("+", "p").replace("-", "m") for b in bins]
    panel = data.set_index(["tag", "week_start"])
    res = PanelOLS(
        panel[outcome],
        panel[exog_cols],
        entity_effects=True,
        time_effects=True,
    ).fit(cov_type="clustered", cluster_entity=True)

    rows = []
    for b, col in zip(bins, exog_cols):
        rows.append(
            {
                "relative_week_bin": b,
                "estimate": res.params[col],
                "std_error": res.std_errors[col],
                "ci_low": res.params[col] - 1.96 * res.std_errors[col],
                "ci_high": res.params[col] + 1.96 * res.std_errors[col],
                "omitted_bin": omitted,
                "outcome": outcome,
                "bin_width": bin_width,
            }
        )
    return pd.DataFrame(rows)


def plot_time_series(df: pd.DataFrame, output: Path) -> None:
    weekly = (
        df.groupby("week_start", as_index=False)
        .agg(questions=("questions", "sum"), answers=("answers", "sum"), avg_body_length=("avg_body_length", "mean"))
        .sort_values("week_start")
    )
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    specs = [("questions", "Questions"), ("answers", "Answers"), ("avg_body_length", "Avg. body length")]
    for ax, (col, label) in zip(axes, specs):
        ax.plot(weekly["week_start"], weekly[col], color="#1f4e79", linewidth=1.3)
        ax.axvline(pd.Timestamp(CHATGPT_RELEASE_DATE), color="#9f1d20", linestyle="--", linewidth=1)
        ax.set_ylabel(label)
    axes[-1].set_xlabel("Week")
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200)
    plt.close(fig)


def plot_event_study(event: pd.DataFrame, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axhline(0, color="black", linewidth=0.8)
    ax.axvline(0, color="#9f1d20", linestyle="--", linewidth=1)
    ax.plot(event["relative_week_bin"], event["estimate"], color="#1f4e79", linewidth=1.3)
    ax.fill_between(
        event["relative_week_bin"],
        event["ci_low"],
        event["ci_high"],
        color="#1f4e79",
        alpha=0.18,
        linewidth=0,
    )
    ax.set_xlabel("Weeks relative to ChatGPT release, 4-week bins")
    ax.set_ylabel("Coefficient on AI-answerability")
    ax.set_title("Event study: log(1 + questions)")
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200)
    plt.close(fig)


def run(input_path: Path, tables_dir: Path, figures_dir: Path) -> dict[str, Path]:
    df = load_panel(input_path)
    outputs = descriptive_tables(df, tables_dir)
    did = estimate_did(df)
    event = estimate_event_study(df)
    outputs["did"] = tables_dir / "stackoverflow_did_real.csv"
    outputs["event"] = tables_dir / "stackoverflow_event_study_log_questions_real.csv"
    write_csv(did, outputs["did"])
    write_csv(event, outputs["event"])
    outputs["time_series_fig"] = figures_dir / "stackoverflow_real_time_series.png"
    outputs["event_fig"] = figures_dir / "stackoverflow_event_study_log_questions_real.png"
    plot_time_series(df, outputs["time_series_fig"])
    plot_event_study(event, outputs["event_fig"])
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run first-pass real Stack Overflow descriptive and DID results.")
    parser.add_argument("--input", type=Path, default=PROCESSED_DIR / "stackoverflow_tag_week_panel_real.csv")
    parser.add_argument("--tables-dir", type=Path, default=TABLES_DIR)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DIR)
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    outputs = run(args.input, args.tables_dir, args.figures_dir)
    for key, path in outputs.items():
        logger.info("Wrote %s to %s", key, path)


if __name__ == "__main__":
    main()
