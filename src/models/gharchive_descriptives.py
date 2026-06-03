import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.config import CHATGPT_RELEASE_DATE
from src.paths import FIGURES_DIR, PROCESSED_DIR, TABLES_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


KEY_EVENTS = ["PullRequestEvent", "IssuesEvent", "IssueCommentEvent", "ForkEvent", "CreateEvent", "PushEvent"]


def load_panel(path: Path) -> pd.DataFrame:
    df = read_csv(path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["post_chatgpt"] = df["week_start"] >= pd.Timestamp(CHATGPT_RELEASE_DATE)
    return df.sort_values(["week_start", "event_type"])


def build_prepost(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.assign(period=df["post_chatgpt"].map({False: "pre", True: "post"}))
        .groupby(["period", "event_type"], as_index=False)
        .agg(
            weeks=("week_start", "nunique"),
            events=("events", "sum"),
            first_seen_actors=("first_seen_actors_in_sample", "sum"),
            first_seen_repos=("first_seen_repos_in_sample", "sum"),
        )
        .assign(
            events_per_week=lambda d: d["events"] / d["weeks"],
            first_seen_actors_per_week=lambda d: d["first_seen_actors"] / d["weeks"],
            first_seen_repos_per_week=lambda d: d["first_seen_repos"] / d["weeks"],
        )
        .sort_values(["event_type", "period"])
    )


def build_weekly_totals(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("week_start", as_index=False)
        .agg(
            events=("events", "sum"),
            first_seen_actors=("first_seen_actors_in_sample", "sum"),
            first_seen_repos=("first_seen_repos_in_sample", "sum"),
        )
        .sort_values("week_start")
    )


def build_event_weekly(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["event_type"].isin(KEY_EVENTS)].copy()


def plot_total_series(weekly: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    specs = [
        ("events", "Events"),
        ("first_seen_actors", "First-seen actors"),
        ("first_seen_repos", "First-seen repos"),
    ]
    for ax, (col, label) in zip(axes, specs):
        ax.plot(weekly["week_start"], weekly[col], color="#1f4e79", linewidth=1.2)
        ax.axvline(pd.Timestamp(CHATGPT_RELEASE_DATE), color="#9f1d20", linestyle="--", linewidth=1)
        ax.set_ylabel(label)
    axes[-1].set_xlabel("Week")
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200)
    plt.close(fig)


def plot_event_type_series(event_weekly: pd.DataFrame, metric: str, output: Path) -> None:
    pivot = event_weekly.pivot_table(index="week_start", columns="event_type", values=metric, aggfunc="sum").fillna(0)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    colors = ["#1f4e79", "#8a4f7d", "#3b7a57", "#b45f06", "#6c757d", "#9f1d20"]
    for event_type, color in zip(KEY_EVENTS, colors):
        if event_type in pivot.columns:
            ax.plot(pivot.index, pivot[event_type], linewidth=1.1, label=event_type.replace("Event", ""), color=color)
    ax.axvline(pd.Timestamp(CHATGPT_RELEASE_DATE), color="black", linestyle="--", linewidth=1)
    ax.set_ylabel(metric.replace("_", " ").title())
    ax.set_xlabel("Week")
    ax.legend(ncol=3, fontsize=8)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200)
    plt.close(fig)


def run(input_path: Path, tables_dir: Path, figures_dir: Path) -> dict[str, Path]:
    df = load_panel(input_path)
    prepost = build_prepost(df)
    weekly = build_weekly_totals(df)
    event_weekly = build_event_weekly(df)

    outputs = {
        "prepost": tables_dir / "gharchive_prepost_descriptives.csv",
        "weekly": tables_dir / "gharchive_weekly_totals.csv",
        "event_weekly": tables_dir / "gharchive_event_weekly.csv",
        "total_fig": figures_dir / "gharchive_total_weekly_series.png",
        "events_fig": figures_dir / "gharchive_events_by_type_weekly.png",
        "actors_fig": figures_dir / "gharchive_first_seen_actors_by_type_weekly.png",
    }
    write_csv(prepost, outputs["prepost"])
    write_csv(weekly, outputs["weekly"])
    write_csv(event_weekly, outputs["event_weekly"])
    plot_total_series(weekly, outputs["total_fig"])
    plot_event_type_series(event_weekly, "events", outputs["events_fig"])
    plot_event_type_series(event_weekly, "first_seen_actors_in_sample", outputs["actors_fig"])
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build descriptive tables and figures for sampled GH Archive panel.")
    parser.add_argument(
        "--input",
        type=Path,
        default=PROCESSED_DIR / "gharchive" / "gharchive_mon_thu_12utc_2021_2024_week_event_panel.csv",
    )
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
