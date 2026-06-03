import argparse

from src.paths import RAW_DIR, ensure_directories
from src.utils.logging_utils import get_logger


def main() -> None:
    parser = argparse.ArgumentParser(description="Document manual Stack Exchange Data Explorer downloads.")
    parser.add_argument("--output-dir", default=RAW_DIR / "stackoverflow")
    args = parser.parse_args()
    ensure_directories()
    logger = get_logger(__name__)
    logger.info("Stack Exchange data are downloaded manually from SEDE.")
    logger.info("Save exported CSV files in %s using names documented in sql/README.md", args.output_dir)


if __name__ == "__main__":
    main()
