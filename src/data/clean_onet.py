import argparse
from pathlib import Path

import pandas as pd

from src.paths import EXTERNAL_DIR, PROCESSED_DIR, ensure_directories
from src.utils.io import write_csv
from src.utils.logging_utils import get_logger


DEFAULT_TABLES = {
    "occupations": "Occupation Data.txt",
    "skills": "Skills.txt",
    "knowledge": "Knowledge.txt",
    "tasks": "Task Statements.txt",
    "job_zones": "Job Zones.txt",
    "tech_skills": "Technology Skills.txt",
}


def read_onet_table(input_dir: Path, filename: str) -> pd.DataFrame:
    path = input_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing O*NET table: {path}")
    return pd.read_csv(path, sep="\t", dtype=str)


def clean_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = (
        out.columns.str.strip()
        .str.lower()
        .str.replace("*", "", regex=False)
        .str.replace("/", "_", regex=False)
        .str.replace("-", "_", regex=False)
        .str.replace(" ", "_", regex=False)
    )
    for col in out.columns:
        out[col] = out[col].astype(str).str.strip()
    return out


def clean_onet(input_dir: Path, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for table_name, filename in DEFAULT_TABLES.items():
        df = clean_table(read_onet_table(input_dir, filename))
        output = output_dir / f"onet_{table_name}.csv"
        write_csv(df, output)
        outputs[table_name] = output
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean selected O*NET text tables into CSV files.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=EXTERNAL_DIR / "onet" / "db_30_2_text" / "db_30_2_text",
    )
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DIR / "onet")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    outputs = clean_onet(args.input_dir, args.output_dir)
    for name, path in outputs.items():
        logger.info("Wrote O*NET %s table to %s", name, path)


if __name__ == "__main__":
    main()
