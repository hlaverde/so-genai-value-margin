import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.paths import FIGURES_DIR, PROCESSED_DIR, ensure_directories
from src.utils.io import read_csv
from src.utils.logging_utils import get_logger


def plot_time_series(df: pd.DataFrame, outcome: str, output: Path) -> None:
    data = df.copy()
    data["week_start"] = pd.to_datetime(data["week_start"])
    weekly = data.groupby("week_start", as_index=False)[outcome].sum()
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(weekly["week_start"], weekly[outcome], color="#2b6cb0", linewidth=1.5)
    ax.axvline(pd.Timestamp("2022-11-30"), color="#c53030", linestyle="--", linewidth=1)
    ax.set_xlabel("Week")
    ax.set_ylabel(outcome)
    ax.set_title(f"Stack Overflow {outcome} over time")
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot aggregate Stack Overflow time series.")
    parser.add_argument("--input", type=Path, default=PROCESSED_DIR / "stackoverflow_tag_week_panel.csv")
    parser.add_argument("--outcome", default="questions")
    parser.add_argument("--output", type=Path, default=FIGURES_DIR / "stackoverflow_questions_time_series.png")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    plot_time_series(read_csv(args.input), args.outcome, args.output)
    logger.info("Wrote figure to %s", args.output)


if __name__ == "__main__":
    main()
