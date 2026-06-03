"""External validation of substitutability with zero-shot classifier.

Uses an MNLI cross-encoder (DeBERTa-v3-base) as an independent
external validator. The cross-encoder evaluates each question
title against the natural-language hypothesis
``This is a substitutable programming question that an LLM
could answer well.'' and returns an entailment probability
that we use as the external label.

Cross-encoders are trained on a different objective (NLI) than
the sentence-similarity embedding models, and are not seed-based,
so they provide a more independent external signal than the
embedding centroids of the main analysis.

Output:
    outputs/tables/rp_validation_zeroshot.csv
    outputs/tables/rp_validation_zeroshot_kappa.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score


SEED = 20251122
SUBSTITUTABLE = {
    "short_code", "long_code", "how_to", "debugging_simple",
    "other_conceptual",
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--sample",
        type=Path,
        default=Path("outputs/tables/rp_validation_strong_sample.csv"),
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("outputs/tables"),
    )
    p.add_argument("--n-eval", type=int, default=500)
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    sample = pd.read_csv(args.sample)
    print(f"Loaded {len(sample)} previously-classified questions")

    # Take a random sub-sample for the expensive cross-encoder
    rng = np.random.default_rng(SEED)
    if len(sample) > args.n_eval:
        idx = rng.choice(len(sample), size=args.n_eval, replace=False)
        sample = sample.iloc[idx].reset_index(drop=True)
    print(f"Running zero-shot validator on {len(sample)} titles")

    # Use a zero-shot classification pipeline
    from transformers import pipeline

    classifier = pipeline(
        "zero-shot-classification",
        model="cross-encoder/nli-deberta-v3-base",
    )
    labels = [
        "a routine programming task that a large language model could answer well",
        "a version-specific or architecture-design question that depends on context",
    ]
    titles = sample["title"].tolist()
    print("Classifying...")
    preds = classifier(titles, candidate_labels=labels, batch_size=16)
    if isinstance(preds, dict):
        preds = [preds]
    sample["zeroshot_label"] = [
        "substitutable" if p["labels"][0] == labels[0] else "non_substitutable"
        for p in preds
    ]
    sample["zeroshot_substitutable_prob"] = [
        p["scores"][p["labels"].index(labels[0])] for p in preds
    ]
    sample["zeroshot_sub"] = (sample["zeroshot_label"] == "substitutable").astype(int)

    # Compare against heuristic
    k_h_vs_zs = cohen_kappa_score(sample["heuristic_sub"], sample["zeroshot_sub"])
    k_minilm_vs_zs = cohen_kappa_score(sample["minilm_sub"], sample["zeroshot_sub"])
    k_mpnet_vs_zs = cohen_kappa_score(sample["mpnet_sub"], sample["zeroshot_sub"])
    print()
    print(f"Cohen's kappa heuristic vs zero-shot: {k_h_vs_zs:.3f}")
    print(f"Cohen's kappa MiniLM vs zero-shot:    {k_minilm_vs_zs:.3f}")
    print(f"Cohen's kappa MPNet vs zero-shot:     {k_mpnet_vs_zs:.3f}")

    # Save
    out_csv = args.out_dir / "rp_validation_zeroshot.csv"
    sample.to_csv(out_csv, index=False)
    print(f"saved {out_csv}")

    pd.DataFrame([
        {"comparison": "heuristic_vs_zeroshot",  "kappa": k_h_vs_zs,    "n": len(sample)},
        {"comparison": "minilm_vs_zeroshot",     "kappa": k_minilm_vs_zs, "n": len(sample)},
        {"comparison": "mpnet_vs_zeroshot",      "kappa": k_mpnet_vs_zs,  "n": len(sample)},
    ]).to_csv(args.out_dir / "rp_validation_zeroshot_kappa.csv", index=False)
    print(f"saved {args.out_dir / 'rp_validation_zeroshot_kappa.csv'}")


if __name__ == "__main__":
    main()
