"""
Zero-cost embedding-based external validation of the AI-answerability
structural index.

The structural index in the paper (ai_answerability_structural) is built
from pre-treatment Stack Overflow features only (frequency, accepted
rate, maturity).  An adversarial referee can object that this measures
historical popularity, not LLM-answerability per se.

This script provides an independent embedding-based score:

    1. Sample N=1,000 random pre-ChatGPT questions from raw.
    2. Compute a sentence-transformer embedding for each question title.
    3. Compute embeddings for 12 exemplar prompts: 6 that frontier LLMs
       answer well (short-code, how-to, syntax), 6 that frontier LLMs
       cannot answer without private/local context (specific stack
       traces with private file paths, environment-specific configs,
       repository-specific architecture).
    4. Per question: similarity to easy exemplars minus similarity to
       hard exemplars -> "LLM-answerability score".
    5. Aggregate by tag (mean score over questions of that tag).
    6. Correlate with the structural index used in the DDD.
    7. Report Pearson and Spearman, and top/bottom tags.

This is an *embedding-based* validation, not a frontier-LLM judgement.
The contribution is to show that an independent text-based measure
correlates positively with the historical-feature-based index.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.paths import OUTPUTS_DIR, PROCESSED_DIR, RAW_DIR  # noqa: E402

RAW_SO_DIR = RAW_DIR / "stackoverflow"
AI_ANSWERABILITY = PROCESSED_DIR / "ai_answerability_real.csv"
MODELS_DIR = OUTPUTS_DIR / "models"
TABLES_DIR = OUTPUTS_DIR / "tables"
DIAG_DIR = OUTPUTS_DIR / "diagnostics"
for _d in (MODELS_DIR, TABLES_DIR, DIAG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

SAMPLE_N = 1000
SEED = 20260527
CUTOFF = pd.Timestamp("2022-11-30")

# Exemplar prompts representing the two ends of the LLM-answerability
# spectrum.  These were generated independently of the DDD design.
EXEMPLARS_EASY = [
    "How do I reverse a string in Python?",
    "What is the syntax for a for-loop in JavaScript?",
    "How do I parse JSON in Java?",
    "How can I sort a list of dictionaries by a key in Python?",
    "How do I write a basic React functional component?",
    "What is the difference between map and forEach in JavaScript?",
]
EXEMPLARS_HARD = [
    "My company-specific build pipeline crashes with code 137 only on "
    "our internal CI runner after Kubernetes 1.27 upgrade",
    "Why does our custom CUDA kernel deadlock on our A100 when launched "
    "from PyTorch 2.0.1 in our private cluster",
    "Our legacy authentication microservice returns 503 only when "
    "called from container deployed to our Tencent Cloud production "
    "environment with cilium CNI",
    "Specific version conflict between our internal protobuf fork and "
    "grpc 1.58 on RHEL 8 with FIPS mode enabled",
    "Architecture decision: should we use saga or two-phase commit for "
    "our specific event-sourced inventory system with current Kafka "
    "topology",
    "Compiler error on private toolchain when cross-compiling proprietary "
    "firmware for our internal RISC-V SoC under Yocto Honister",
]


def load_raw_sample() -> pd.DataFrame:
    """Random sample of N pre-ChatGPT questions across all raw files."""
    print(f"[load_raw] scanning raw files ...")
    files = sorted(RAW_SO_DIR.glob("stackoverflow_question_type_raw_*.csv"))
    pre_files = []
    for f in files:
        # Heuristic: file name encodes week range; only keep files whose
        # last date is strictly before the ChatGPT cutoff.
        name = f.stem
        # e.g. stackoverflow_question_type_raw_2022-07-09_2022-07-13
        date_parts = name.split("_")[-2:]
        try:
            d = pd.Timestamp(date_parts[-1])
            if d < CUTOFF:
                pre_files.append(f)
        except Exception:
            pre_files.append(f)
    print(f"[load_raw] {len(pre_files)} pre-cutoff files")

    rng = np.random.default_rng(SEED)
    chosen = rng.choice(pre_files, size=min(20, len(pre_files)),
                        replace=False)
    print(f"[load_raw] sampling from {len(chosen)} files")
    frames = []
    for f in chosen:
        try:
            df = pd.read_csv(f, usecols=["tag", "week_start", "question_id",
                                         "title", "body_length", "has_code"])
            frames.append(df)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {f.name}: {exc}")
    raw = pd.concat(frames, ignore_index=True)
    raw["week_start"] = pd.to_datetime(raw["week_start"], errors="coerce")
    raw = raw[raw["week_start"] < CUTOFF]
    raw = raw.dropna(subset=["title"])
    raw = raw[raw["title"].str.len() > 5]
    print(f"[load_raw] {len(raw):,} pre-cutoff rows pooled; sampling "
          f"N={SAMPLE_N} questions")
    sample = raw.sample(n=min(SAMPLE_N, len(raw)), random_state=SEED)
    return sample.reset_index(drop=True)


def compute_embeddings(texts: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer
    print(f"[embed] loading sentence-transformer model ...")
    # all-MiniLM-L6-v2: small, fast, downloaded once
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print(f"[embed] encoding {len(texts)} texts ...")
    return model.encode(texts, batch_size=32, show_progress_bar=False,
                        normalize_embeddings=True)


def main():
    print(f"[main] start {datetime.now().isoformat(timespec='seconds')}")
    sample = load_raw_sample()
    print(f"[main] sample: {len(sample):,} questions, "
          f"{sample['tag'].nunique()} unique tags")

    titles = sample["title"].astype(str).tolist()
    easy_emb = compute_embeddings(EXEMPLARS_EASY)
    hard_emb = compute_embeddings(EXEMPLARS_HARD)
    print(f"[main] easy_emb shape: {easy_emb.shape}; "
          f"hard_emb shape: {hard_emb.shape}")
    q_emb = compute_embeddings(titles)
    print(f"[main] q_emb shape: {q_emb.shape}")

    # Mean cosine sim to each exemplar set (embeddings already normalised
    # so dot product = cosine similarity)
    sim_easy = q_emb @ easy_emb.T  # (N, 6)
    sim_hard = q_emb @ hard_emb.T  # (N, 6)
    mean_easy = sim_easy.mean(axis=1)
    mean_hard = sim_hard.mean(axis=1)
    score = mean_easy - mean_hard  # higher = more LLM-answerable
    sample["embed_easy_sim"] = mean_easy
    sample["embed_hard_sim"] = mean_hard
    sample["embed_llm_answerability"] = score

    # Aggregate by tag
    tag_score = sample.groupby("tag")["embed_llm_answerability"].agg(
        ["mean", "count"]).reset_index()
    tag_score.columns = ["tag", "embed_answerability_mean", "n_questions"]
    print(f"[main] {len(tag_score)} unique tags with mean embedding score")

    # Merge with structural index
    ai = pd.read_csv(AI_ANSWERABILITY)
    merged = tag_score.merge(
        ai[["tag", "ai_answerability_structural", "ai_answerability_zscore",
            "ai_answerability_pca", "ai_answerability_quantile"]],
        on="tag", how="inner",
    )
    print(f"[main] {len(merged)} tags after merge with structural index")

    # Correlations
    from scipy.stats import pearsonr, spearmanr
    corr_results = []
    for col in ["ai_answerability_structural", "ai_answerability_zscore",
                "ai_answerability_pca", "ai_answerability_quantile"]:
        p, p_p = pearsonr(merged["embed_answerability_mean"], merged[col])
        s, s_p = spearmanr(merged["embed_answerability_mean"], merged[col])
        corr_results.append({
            "structural_var": col,
            "pearson_r": p, "pearson_p": p_p,
            "spearman_r": s, "spearman_p": s_p,
        })
    corr_df = pd.DataFrame(corr_results)
    corr_df.to_csv(MODELS_DIR / "embedding_validation_correlations.csv",
                   index=False)
    print(f"\n[main] Correlations between embedding score and "
          f"structural index variants:\n{corr_df}")

    # Top/bottom tags by embedding score
    sorted_tags = merged.sort_values("embed_answerability_mean",
                                     ascending=False)
    top5 = sorted_tags.head(5)
    bot5 = sorted_tags.tail(5)
    print(f"\nTop 5 tags by embedding score (more LLM-answerable):")
    print(top5[["tag", "embed_answerability_mean",
                "ai_answerability_structural", "n_questions"]].to_string(
        index=False))
    print(f"\nBottom 5 tags by embedding score:")
    print(bot5[["tag", "embed_answerability_mean",
                "ai_answerability_structural", "n_questions"]].to_string(
        index=False))

    # Build LaTeX table
    lines = [
        r"\begin{table}[ht]", r"\centering",
        r"\caption{Embedding-based external validation of the "
        r"AI-answerability proxy. For each tag we compute the mean "
        r"cosine-similarity differential of a random sample of "
        r"pre-ChatGPT questions against two sets of exemplar prompts: "
        r"six that a frontier LLM answers well (short syntactic and "
        r"how-to questions) and six that require private or "
        r"organisation-specific context that a frontier LLM cannot "
        r"reproduce. The mean differential is then correlated with the "
        r"four pre-treatment AI-answerability index variants. Positive "
        r"correlation indicates that the historical-feature-based index "
        r"is consistent with an independent embedding-based proxy. "
        r"Embeddings: \texttt{sentence-transformers all-MiniLM-L6-v2}, "
        r"$N = " + str(SAMPLE_N) + r"$ pre-ChatGPT questions.}",
        r"\label{tab:embedding_validation}",
        r"\small",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Structural index variant & Pearson $r$ & $p$ & Spearman $\rho$ & $p$ \\",
        r"\midrule",
    ]
    for _, r in corr_df.iterrows():
        nice = r["structural_var"].replace("ai_answerability_", "").capitalize()
        lines.append(
            f"{nice} & {r['pearson_r']:.3f} & {r['pearson_p']:.4f} & "
            f"{r['spearman_r']:.3f} & {r['spearman_p']:.4f} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    (TABLES_DIR / "table_embedding_validation.tex").write_text(
        "\n".join(lines), encoding="utf-8")
    print(f"\nsaved {TABLES_DIR / 'table_embedding_validation.tex'}")

    # Save merged tag-level data
    merged.to_csv(MODELS_DIR / "embedding_validation_tag_scores.csv",
                  index=False)

    # Diagnostic note
    diag = DIAG_DIR / "embedding_validation_audit.md"
    lines = [
        "# Embedding-based external validation of AI-answerability proxy\n",
        f"_Generated: {datetime.now().isoformat(timespec='seconds')}_\n\n",
        f"## Sample\n\n- N = {SAMPLE_N} random pre-ChatGPT questions\n",
        f"- {len(tag_score)} unique tags represented\n",
        f"- {len(merged)} tags matched with structural index\n\n",
        "## Exemplar prompts\n\n",
        "**Easy (high LLM-answerability expected):**\n",
        *[f"- {e}\n" for e in EXEMPLARS_EASY],
        "\n**Hard (low LLM-answerability expected):**\n",
        *[f"- {e}\n" for e in EXEMPLARS_HARD],
        "\n## Correlations\n\n", corr_df.to_markdown(index=False),
        "\n\n## Top-5 tags by embedding score\n\n",
        top5[["tag", "embed_answerability_mean",
              "ai_answerability_structural", "n_questions"]].to_markdown(
            index=False),
        "\n\n## Bottom-5 tags by embedding score\n\n",
        bot5[["tag", "embed_answerability_mean",
              "ai_answerability_structural", "n_questions"]].to_markdown(
            index=False),
    ]
    diag.write_text("\n".join(lines), encoding="utf-8")
    print(f"saved {diag}")
    print(f"\n[main] done {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
