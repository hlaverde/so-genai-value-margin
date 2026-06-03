import argparse
from pathlib import Path

import pandas as pd

from src.config import EXPECTED_STACKOVERFLOW_FILES
from src.paths import RAW_DIR, ensure_directories
from src.utils.io import write_csv
from src.utils.logging_utils import get_logger


WINDOW_PATTERNS = {
    "tag_week": "stackoverflow_tag_week_*.csv",
    "user_tag_week": "stackoverflow_user_tag_week_*.csv",
    "post_complexity": "stackoverflow_post_complexity_*.csv",
}


def combine_pattern(input_dir: Path, pattern: str) -> pd.DataFrame:
    paths = sorted(input_dir.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No files found for pattern {pattern} in {input_dir}")
    frames = []
    for path in paths:
        frame = pd.read_csv(path)
        frame["source_file"] = path.name
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def combine_stackoverflow_windows(input_dir: Path, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for key, pattern in WINDOW_PATTERNS.items():
        df = combine_pattern(input_dir, pattern)
        if "source_file" in df.columns:
            df = df.drop(columns=["source_file"])
        df = df.drop_duplicates()
        output = output_dir / EXPECTED_STACKOVERFLOW_FILES[key]
        write_csv(df, output)
        outputs[key] = output
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Combine manually exported SEDE window CSV files.")
    parser.add_argument("--input-dir", type=Path, default=RAW_DIR / "stackoverflow" / "windows")
    parser.add_argument("--output-dir", type=Path, default=RAW_DIR / "stackoverflow")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    outputs = combine_stackoverflow_windows(args.input_dir, args.output_dir)
    for key, path in outputs.items():
        logger.info("Wrote combined %s CSV to %s", key, path)


if __name__ == "__main__":
    main()
