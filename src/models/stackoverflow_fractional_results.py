import argparse
from pathlib import Path

import pandas as pd
from linearmodels.panel import PanelOLS

from src.paths import PROCESSED_DIR, TABLES_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


def did(df: pd.DataFrame, outcome: str) -> dict[str, object]:
    data = df.dropna(subset=["ai_answerability_zscore", outcome]).copy()
    data["ai_x_post"] = data["ai_answerability_zscore"] * data["post_chatgpt"].astype(int)
    panel = data.set_index(["tag", "week_start"])
    res = PanelOLS(
        panel[outcome],
        panel[["ai_x_post"]],
        entity_effects=True,
        time_effects=True,
    ).fit(cov_type="clustered", cluster_entity=True)
    return {
        "measurement": "fractional_count",
        "outcome": outcome,
        "estimate": res.params["ai_x_post"],
        "std_error": res.std_errors["ai_x_post"],
        "t_stat": res.tstats["ai_x_post"],
        "p_value": res.pvalues["ai_x_post"],
        "n_obs": int(res.nobs),
        "n_tags": int(data["tag"].nunique()),
    }


def run(input_path: Path, output: Path) -> pd.DataFrame:
    df = read_csv(input_path, parse_dates=["week_start"])
    rows = [did(df, outcome) for outcome in ["log_questions", "log_answers", "log_unique_users", "log_accepted_answers"]]
    out = pd.DataFrame(rows)
    write_csv(out, output)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stack Overflow DID on fractional-count panel.")
    parser.add_argument("--input", type=Path, default=PROCESSED_DIR / "stackoverflow_fractional_tag_week_panel_real.csv")
    parser.add_argument("--output", type=Path, default=TABLES_DIR / "stackoverflow_fractional_did_real.csv")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    out = run(args.input, args.output)
    logger.info("Wrote fractional DID to %s", args.output)
    logger.info("\n%s", out.to_string(index=False))


if __name__ == "__main__":
    main()
