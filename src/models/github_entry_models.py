import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from src.paths import PROCESSED_DIR, TABLES_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


LANGUAGE_NORMALIZATION = {
    "c#": "csharp",
    "c++": "cpp",
    "javascript": "javascript",
    "typescript": "typescript",
    "python": "python",
    "html": "html",
    "css": "css",
    "java": "java",
    "php": "php",
    "shell": "shell",
    "go": "go",
    "ruby": "ruby",
    "r": "r",
}


def normalize_language(value: str) -> str:
    value = str(value).strip().lower()
    return LANGUAGE_NORMALIZATION.get(value, value)


def prepare_language_week_panel(language_panel_path: Path, so_dependence_path: Path) -> pd.DataFrame:
    gh = read_csv(language_panel_path, parse_dates=["week_start"])
    so = read_csv(so_dependence_path)
    gh["language"] = gh["language"].map(normalize_language)
    so["language"] = so["language"].map(normalize_language)

    weekly = (
        gh.groupby(["language", "week_start"], as_index=False)
        .agg(
            events=("events", "sum"),
            active_actors=("active_actors", "sum"),
            first_seen_actors_language=("first_seen_actors_language", "sum"),
            first_seen_actors_language_event=("first_seen_actors_language_event", "sum"),
        )
    )
    pr_weekly = (
        gh[gh["event_type"].eq("PullRequestEvent")]
        .groupby(["language", "week_start"], as_index=False)
        .agg(
            pr_events=("events", "sum"),
            pr_active_actors=("active_actors", "sum"),
            pr_first_seen_actors=("first_seen_actors_language_event", "sum"),
        )
    )
    issue_weekly = (
        gh[gh["event_type"].isin(["IssuesEvent", "IssueCommentEvent"])]
        .groupby(["language", "week_start"], as_index=False)
        .agg(
            issue_events=("events", "sum"),
            issue_active_actors=("active_actors", "sum"),
            issue_first_seen_actors=("first_seen_actors_language_event", "sum"),
        )
    )
    weekly = weekly.merge(pr_weekly, on=["language", "week_start"], how="left")
    weekly = weekly.merge(issue_weekly, on=["language", "week_start"], how="left")

    languages = sorted(weekly["language"].unique())
    weeks = pd.date_range(weekly["week_start"].min(), weekly["week_start"].max(), freq="W-MON")
    balanced = pd.MultiIndex.from_product([languages, weeks], names=["language", "week_start"]).to_frame(index=False)
    out = balanced.merge(weekly, on=["language", "week_start"], how="left")
    count_cols = [c for c in out.columns if c not in {"language", "week_start"}]
    out[count_cols] = out[count_cols].fillna(0)

    so_cols = ["language", "so_questions_pre", "mapped_tags", "so_dependence_share", "so_dependence_log", "so_dependence_rank"]
    out = out.merge(so[so_cols], on="language", how="inner")
    out["post_chatgpt"] = (out["week_start"] >= pd.Timestamp("2022-11-30")).astype(int)
    out["year"] = out["week_start"].dt.year
    for col in count_cols:
        out[f"log1p_{col}"] = np.log1p(out[col])
    return out


def fit_fe_model(df: pd.DataFrame, outcome: str, treatment: str) -> dict[str, float | str | int]:
    model_df = df.copy()
    model_df["treat_post"] = model_df[treatment] * model_df["post_chatgpt"]
    formula = f"{outcome} ~ treat_post + C(language) + C(week_start)"
    fit = smf.ols(formula, data=model_df).fit(cov_type="cluster", cov_kwds={"groups": model_df["language"]})
    return {
        "outcome": outcome,
        "treatment": treatment,
        "coefficient": fit.params.get("treat_post", np.nan),
        "std_error_cluster_language": fit.bse.get("treat_post", np.nan),
        "p_value": fit.pvalues.get("treat_post", np.nan),
        "n_obs": int(fit.nobs),
        "n_languages": int(model_df["language"].nunique()),
        "adj_r2": fit.rsquared_adj,
    }


def run_models(panel: pd.DataFrame) -> pd.DataFrame:
    outcomes = [
        "log1p_events",
        "log1p_active_actors",
        "log1p_first_seen_actors_language",
        "log1p_pr_events",
        "log1p_pr_first_seen_actors",
        "log1p_issue_events",
        "log1p_issue_first_seen_actors",
    ]
    treatments = ["so_dependence_log", "so_dependence_rank"]
    rows = []
    for treatment in treatments:
        for outcome in outcomes:
            rows.append(fit_fe_model(panel, outcome, treatment))
    return pd.DataFrame(rows)


def summarize_panel(panel: pd.DataFrame) -> pd.DataFrame:
    return (
        panel.groupby("language", as_index=False)
        .agg(
            weeks=("week_start", "nunique"),
            events=("events", "sum"),
            active_actors=("active_actors", "sum"),
            first_seen_actors_language=("first_seen_actors_language", "sum"),
            pr_events=("pr_events", "sum"),
            pr_first_seen_actors=("pr_first_seen_actors", "sum"),
            issue_events=("issue_events", "sum"),
            issue_first_seen_actors=("issue_first_seen_actors", "sum"),
            so_dependence_log=("so_dependence_log", "first"),
            so_dependence_rank=("so_dependence_rank", "first"),
        )
        .sort_values("events", ascending=False)
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exploratory GitHub language-week entry models joined to SO dependence.")
    parser.add_argument(
        "--language-panel",
        type=Path,
        default=PROCESSED_DIR / "gharchive" / "gharchive_top50_repo_language_week_event_panel.csv",
    )
    parser.add_argument("--so-dependence", type=Path, default=PROCESSED_DIR / "so_dependence_language.csv")
    parser.add_argument("--panel-output", type=Path, default=PROCESSED_DIR / "gharchive" / "gharchive_top50_language_week_so_panel.csv")
    parser.add_argument("--summary-output", type=Path, default=TABLES_DIR / "github_top50_language_panel_summary.csv")
    parser.add_argument("--model-output", type=Path, default=TABLES_DIR / "github_top50_language_entry_models.csv")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    panel = prepare_language_week_panel(args.language_panel, args.so_dependence)
    summary = summarize_panel(panel)
    models = run_models(panel)
    write_csv(panel, args.panel_output)
    write_csv(summary, args.summary_output)
    write_csv(models, args.model_output)
    logger.info("Wrote panel to %s (%s rows, %s languages)", args.panel_output, len(panel), panel["language"].nunique())
    logger.info("Wrote summary to %s", args.summary_output)
    logger.info("Wrote models to %s", args.model_output)
    logger.info("\n%s", summary.to_string(index=False))
    logger.info("\n%s", models.to_string(index=False))


if __name__ == "__main__":
    main()
