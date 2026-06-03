import argparse

from src.paths import EXTERNAL_DIR, ensure_directories
from src.utils.logging_utils import get_logger


def main() -> None:
    parser = argparse.ArgumentParser(description="Document O*NET manual download location.")
    parser.add_argument("--output-dir", default=EXTERNAL_DIR / "onet")
    args = parser.parse_args()
    ensure_directories()
    logger = get_logger(__name__)
    logger.info("Download O*NET database files from https://www.onetcenter.org/database.html")
    logger.info("Save downloaded files in %s and preserve original filenames.", args.output_dir)


if __name__ == "__main__":
    main()
