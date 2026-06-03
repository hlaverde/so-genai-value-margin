import argparse
from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf

from src.paths import PROCESSED_DIR, TABLES_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


def estimate_did(df: pd.DataFrame, outcome: str, treatment: str) -> pd.DataFrame:
    data = df.copy()
    data["post_chatgpt"] = data["post_chatgpt"].astype(int)
    formula = f"{outcome} ~ {treatment}:post_chatgpt + C(tag) + C(week_start)"
    model = smf.ols(formula, data=data).fit(cov_type="cluster", cov_kwds={"groups": data["tag"]})
    term = f"{treatment}:post_chatgpt"
    return pd.DataFrame(
        {
            "model": ["did_stackoverflow"],
            "outcome": [outcome],
            "term": [term],
            "estimate": [model.params.get(term, pd.NA)],
            "std_error": [model.bse.get(term, pd.NA)],
            "p_value": [model.pvalues.get(term, pd.NA)],
            "n_obs": [int(model.nobs)],
        }
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate baseline Stack Overflow DID model.")
    parser.add_argument("--input", type=Path, default=PROCESSED_DIR / "stackoverflow_tag_week_panel.csv")
    parser.add_argument("--outcome", default="questions")
    parser.add_argument("--treatment", default="ai_answerability_zscore")
    parser.add_argument("--output", type=Path, default=TABLES_DIR / "did_stackoverflow.csv")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    out = estimate_did(read_csv(args.input), args.outcome, args.treatment)
    write_csv(out, args.output)
    logger.info("Wrote DID estimate to %s", args.output)


if __name__ == "__main__":
    main()
