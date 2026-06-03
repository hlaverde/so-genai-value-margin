import argparse
import html
import re
from pathlib import Path

import pandas as pd

from src.paths import DOCS_DIR, INTERIM_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


CODING_COLUMNS = [
    "coder_id",
    "human_ai_answerable",
    "basic_howto_debugging",
    "requires_context",
    "sufficient_information",
    "llm_ai_answerable",
    "confidence_1_to_5",
    "notes",
]


def html_to_text(value: str) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    text = re.sub(r"<pre><code>", "\n[CODE]\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</code></pre>", "\n[/CODE]\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<code>", "`", text, flags=re.IGNORECASE)
    text = re.sub(r"</code>", "`", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def make_blind_coding_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["body_plain"] = out["body"].map(html_to_text)
    out["body_excerpt_1500"] = out["body_plain"].str.slice(0, 1500)
    out["codebook_scale"] = "Use 1=yes, 0=no; confidence 1-5"
    for col in CODING_COLUMNS:
        out[col] = ""
    keep = [
        "question_id",
        "creation_date",
        "tag",
        "all_tags",
        "title",
        "body_excerpt_1500",
        "body_plain",
        "body_length",
        "has_code",
        "short_code",
        "how_to_error_title",
        "answer_count",
        "has_accepted_answer",
        "is_closed",
        "minutes_to_first_answer",
        "codebook_scale",
    ] + CODING_COLUMNS
    return out[keep]


def make_key_frame(df: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "question_id",
        "answerability_stratum",
        "tag",
        "ai_answerability_zscore",
        "ai_answerability_pca",
        "ai_answerability_quantile",
        "ai_answerability_structural",
    ]
    return df[keep].copy()


def stratified_pilot(df: pd.DataFrame, n_total: int, seed: int) -> pd.DataFrame:
    strata = list(df["answerability_stratum"].dropna().unique())
    base = n_total // len(strata)
    remainder = n_total % len(strata)
    parts = []
    for i, stratum in enumerate(sorted(strata)):
        n = base + (1 if i < remainder else 0)
        g = df[df["answerability_stratum"].eq(stratum)]
        parts.append(g.sample(min(n, len(g)), random_state=seed + i))
    return pd.concat(parts, ignore_index=True).sample(frac=1, random_state=seed).reset_index(drop=True)


def write_codebook(path: Path) -> None:
    text = """# AI Answerability Coding Codebook

This codebook is for validating the tag-level AI-answerability treatment using question-level coding.

Coders should not use the tag-level AI score or stratum. The coding files are intentionally blind.

## Unit

One Stack Overflow question.

## Coding Variables

Use `1` for yes and `0` for no. Leave blank only if the item cannot be judged.

### `human_ai_answerable`

Would a general-purpose generative AI assistant likely produce a useful answer from the question alone, without complex external context?

Code `1` if:

- the question is self-contained;
- the requested task is a common programming, syntax, API, data manipulation, or debugging issue;
- a model could provide a plausible actionable answer from the title/body/code.

Code `0` if:

- the question depends on hidden local files, credentials, deployment state, private data, or interactive diagnosis;
- the answer requires project-specific architecture decisions;
- the question is ambiguous or underspecified.

### `basic_howto_debugging`

Code `1` if the question is a basic how-to, syntax, simple debugging, common error, or short-code task.

### `requires_context`

Code `1` if the question requires substantial external or local context, such as exact environment, version conflicts, private data, logs not shown, business rules, or system architecture.

### `sufficient_information`

Code `1` if the question includes enough information for a knowledgeable assistant to attempt a useful answer.

### `llm_ai_answerable`

Use this when a coder explicitly asks an LLM or simulates an LLM classification. Code `1` if the LLM judges the question answerable. If no LLM coding is done, leave blank.

### `confidence_1_to_5`

Coder confidence:

- 1 = very uncertain
- 2 = uncertain
- 3 = moderate
- 4 = confident
- 5 = very confident

## Recommended Workflow

1. Code the pilot file first.
2. Compare coders and refine rules.
3. Then code the full file.
4. Save each coder's completed file separately, for example:
   - `ai_answerability_validation_pilot_coder_A.csv`
   - `ai_answerability_validation_pilot_coder_B.csv`
   - `ai_answerability_validation_full_coder_A.csv`
   - `ai_answerability_validation_full_coder_B.csv`

## Validation Metrics

The scoring script computes:

- correlation between tag-level index and human answerability share;
- correlation between tag-level index and LLM answerability share;
- Spearman rank correlation;
- AUC for high-answerability classification;
- Cohen's kappa or Fleiss' kappa across coders.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_files(input_path: Path, output_dir: Path, pilot_n: int, seed: int) -> dict[str, Path]:
    df = read_csv(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    pilot = stratified_pilot(df, pilot_n, seed)
    full_blind = make_blind_coding_frame(df)
    pilot_blind = make_blind_coding_frame(pilot)
    full_key = make_key_frame(df)
    pilot_key = make_key_frame(pilot)

    paths = {
        "pilot_blind": output_dir / "ai_answerability_validation_pilot_blind.csv",
        "pilot_key": output_dir / "ai_answerability_validation_pilot_key.csv",
        "full_blind": output_dir / "ai_answerability_validation_full_blind.csv",
        "full_key": output_dir / "ai_answerability_validation_full_key.csv",
        "codebook": DOCS_DIR / "ai_answerability_coding_codebook.md",
    }
    write_csv(pilot_blind, paths["pilot_blind"])
    write_csv(pilot_key, paths["pilot_key"])
    write_csv(full_blind, paths["full_blind"])
    write_csv(full_key, paths["full_key"])
    write_codebook(paths["codebook"])
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build blind coding files for AI-answerability validation.")
    parser.add_argument("--input", type=Path, default=INTERIM_DIR / "ai_answerability_validation_sample.csv")
    parser.add_argument("--output-dir", type=Path, default=INTERIM_DIR / "validation_coding")
    parser.add_argument("--pilot-n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261130)
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    paths = build_files(args.input, args.output_dir, args.pilot_n, args.seed)
    for name, path in paths.items():
        logger.info("Wrote %s to %s", name, path)


if __name__ == "__main__":
    main()
