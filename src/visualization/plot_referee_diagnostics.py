import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.paths import FIGURES_DIR, TABLES_DIR, ensure_directories
from src.utils.io import read_csv
from src.utils.logging_utils import get_logger


def plot_rolling_placebo_distribution(rolling_path: Path, placebo_path: Path, output: Path) -> None:
    rolling = read_csv(rolling_path)
    placebo = read_csv(placebo_path)
    real = placebo[placebo["placebo_type"].eq("real_chatgpt")]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=False)
    for ax, outcome in zip(axes, ["log_questions", "log_answers"]):
        r = rolling[rolling["outcome"].eq(outcome)]["estimate"].dropna()
        real_est = real[real["outcome"].eq(outcome)]["estimate"].iloc[0]
        ax.hist(r, bins=18, color="#b8c7d9", edgecolor="#34495e")
        ax.axvline(real_est, color="#b22222", linewidth=2.2, label="Real ChatGPT shock")
        ax.axvline(0, color="#333333", linewidth=1, linestyle="--")
        ax.set_title(outcome.replace("_", " "))
        ax.set_xlabel("Placebo coefficient")
        ax.set_ylabel("Count")
        ax.legend(frameon=False)
    fig.suptitle("Rolling placebo distribution, 2019-2022")
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot referee-grade diagnostic figures.")
    parser.add_argument("--rolling", type=Path, default=TABLES_DIR / "referee_rolling_placebos.csv")
    parser.add_argument("--placebo", type=Path, default=TABLES_DIR / "referee_placebo_dates.csv")
    parser.add_argument("--output", type=Path, default=FIGURES_DIR / "referee_rolling_placebo_distribution.png")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    plot_rolling_placebo_distribution(args.rolling, args.placebo, args.output)
    logger.info("Wrote rolling placebo figure to %s", args.output)


if __name__ == "__main__":
    main()
