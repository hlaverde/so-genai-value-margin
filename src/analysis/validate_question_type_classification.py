"""Validación de la clasificación heurística substitutable vs non-substitutable.

Aproximación: usa sentence-transformers (all-MiniLM-L6-v2; ~22 MB) para
embeber títulos de preguntas y los compara con centroides definidos a
partir de seeds. Reporta Cohen's kappa entre clasificador heurístico
y clasificador embedding-based, tanto a nivel 7-category como
binario (substitutable/non-substitutable).

Reproducible: seed fijo; no requiere API ni GPU.

Salidas:
    outputs/tables/rp_validation_question_type.csv
    outputs/tables/rp_validation_kappa.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")
SEED = 20251122

# Seed títulos curados manualmente por categoría
SEEDS = {
    "short_code": [
        "Why does this regex not match digits in python?",
        "How to remove duplicates from a list in JavaScript?",
        "Sorting a Pandas dataframe by column value",
        "How to read a csv into Pandas",
        "Python list comprehension filter elements",
        "JavaScript split string by comma",
        "Convert dictionary to JSON string Python",
        "Get current date in JavaScript",
        "How to reverse a string in Java",
        "Format a number with two decimals",
    ],
    "long_code": [
        "TypeError when running a flask app with multiple endpoints",
        "Spring Boot REST API returns 404 for resource",
        "Reactjs state hook does not update after async fetch",
        "Django model migration fails with foreign key constraint",
        "Node.js Express middleware order causes wrong route handler",
        "Java Stream collect to map ignores duplicate keys",
        "Angular HTTP interceptor not catching errors",
        "Kubernetes pod fails to mount persistent volume",
        "Tensorflow training loop OOM on GPU memory",
        "Spring Security OAuth2 redirect URI mismatch",
    ],
    "how_to": [
        "How to deploy a Django app on AWS Elastic Beanstalk?",
        "How do I authenticate users with Firebase in React?",
        "How can I configure CORS in Express?",
        "How to use environment variables in Docker container?",
        "What is the way to schedule background jobs in Python?",
        "How should I structure folders in a Vue.js project?",
        "How do I migrate a SQL Server database to Postgres?",
        "How to handle JWT refresh tokens in Angular?",
        "How can I integrate Stripe with my Flask app?",
        "How to enable HTTPS for an nginx reverse proxy?",
    ],
    "debugging_simple": [
        "Error: connection refused on port 8080",
        "Unhandled promise rejection in async function",
        "Bug: button onClick fires twice in React",
        "SegFault when running C++ program on Linux",
        "NullPointerException at startup in Spring Boot",
        "TypeError cannot read property of undefined in JS",
        "RuntimeError: tensor sizes mismatch in PyTorch",
        "Crash on Android app launch with Firebase init",
        "Build failed compile error in Visual Studio 2022",
        "Failed to install package via npm: missing dependency",
    ],
    "other_conceptual": [
        "Difference between abstract class and interface in Java",
        "When should I use Redis vs Memcached?",
        "Why is async/await preferred over callbacks?",
        "What does the V in MVC actually do?",
        "When does immutability matter in functional programming?",
        "Difference between unit, integration and end-to-end tests",
        "Why use composition over inheritance?",
        "What is the purpose of dependency injection?",
        "Trade-offs between REST and GraphQL APIs",
        "Why are pure functions important in functional code?",
    ],
    "version_environment_specific": [
        "Python 3.11 incompatible with package X version Y",
        "Configuration of Windows path for Node v18 installation",
        "Ubuntu 20.04 dependency conflict during apt install",
        "macOS Ventura broke my Homebrew Python environment",
        "Docker compose version 3 deprecation warning",
        "Java 17 module path runtime error",
        "Build error Visual Studio 2019 Windows SDK 10 missing",
        "Anaconda environment activation fails in Linux WSL",
        "Compiler runtime mismatch between gcc 11 and 12",
        "Package npm install fails on M1 Mac native arm64",
    ],
    "advanced_architecture": [
        "Best practice for designing microservice boundaries",
        "Scalable distributed message-queue architecture for events",
        "Performance optimization of read-heavy database with sharding",
        "Design pattern for event-driven communication between services",
        "Architectural choice CQRS vs traditional CRUD for high writes",
        "How to design fault-tolerant pipeline in Apache Kafka",
        "Best practice REST API versioning at scale",
        "Distributed cache strategy for multi-region system",
        "Optimization of GraphQL resolver performance",
        "Designing a polyglot persistence layer with multiple databases",
    ],
}

SUBSTITUTABLE = {
    "short_code", "long_code", "how_to", "debugging_simple", "other_conceptual"
}


def kappa_cohen(y1: np.ndarray, y2: np.ndarray) -> float:
    """Cohen's kappa for two categorical assignments."""
    from sklearn.metrics import cohen_kappa_score
    return float(cohen_kappa_score(y1, y2))


def load_sample_questions(raw_dir: Path, n: int = 5000, seed: int = SEED) -> pd.DataFrame:
    """Carga una muestra estratificada por question_type del panel raw 2022-2024."""
    import re

    # Patterns matching prepare_stackoverflow_question_type_raw.py
    VERSION_ENV_PAT = re.compile(
        r"\b(?:version|environment|windows|linux|mac|ubuntu|install|installed|"
        r"configuration|dependency|package|build error|compiler|runtime)\b",
        flags=re.IGNORECASE,
    )
    ADVANCED_PAT = re.compile(
        r"\b(?:architecture|design pattern|scalable|performance|optimization|"
        r"microservice|distributed|best practice)\b",
        flags=re.IGNORECASE,
    )
    DEBUG_PAT = re.compile(
        r"\b(?:error|exception|traceback|not working|bug|debug|failed|failure|"
        r"crash|segmentation fault)\b",
        flags=re.IGNORECASE,
    )
    HOWTO_PAT = re.compile(
        r"\b(?:how to|how do i|how can i|what is the way|how should i)\b",
        flags=re.IGNORECASE,
    )

    def classify(row):
        title = str(row["title"]) if pd.notna(row["title"]) else ""
        body_length = int(row["body_length"]) if pd.notna(row["body_length"]) else 0
        has_code = int(row["has_code"]) if pd.notna(row["has_code"]) else 0
        if VERSION_ENV_PAT.search(title):
            return "version_environment_specific"
        if ADVANCED_PAT.search(title):
            return "advanced_architecture"
        if DEBUG_PAT.search(title):
            return "debugging_simple"
        if HOWTO_PAT.search(title):
            return "how_to"
        if has_code == 1 and body_length <= 1200:
            return "short_code"
        if has_code == 1 and body_length > 1200:
            return "long_code"
        return "other_conceptual"

    # Cargar archivos raw del periodo de interés (2022 Q2 a 2024 Q2)
    files = sorted(raw_dir.glob("stackoverflow_question_type_raw_2022-*.csv")) + \
            sorted(raw_dir.glob("stackoverflow_question_type_raw_2023-*.csv")) + \
            sorted(raw_dir.glob("stackoverflow_question_type_raw_2024-*.csv"))
    frames = []
    for f in files[:40]:  # subset para acelerar
        try:
            frames.append(pd.read_csv(f, usecols=["question_id", "title", "body_length", "has_code"]))
        except Exception:
            continue
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates("question_id").reset_index(drop=True)
    df = df[df["title"].notna() & (df["title"].str.len() > 5)]
    df["heuristic_type"] = df.apply(classify, axis=1)

    # Muestra estratificada
    rng = np.random.default_rng(seed)
    samples = []
    per_cat = n // len(SEEDS)
    for cat in SEEDS.keys():
        sub = df[df["heuristic_type"] == cat]
        if len(sub) == 0:
            continue
        k = min(per_cat, len(sub))
        idx = rng.choice(len(sub), size=k, replace=False)
        samples.append(sub.iloc[idx])
    return pd.concat(samples, ignore_index=True)


def embed_titles(texts: list[str], model_name: str = "all-MiniLM-L6-v2") -> np.ndarray:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name)
    emb = model.encode(texts, batch_size=64, show_progress_bar=True,
                       convert_to_numpy=True, normalize_embeddings=True)
    return emb


def classify_embedding(sample_df: pd.DataFrame) -> pd.DataFrame:
    """Asigna cada título al centroide más cercano (cosine)."""
    titles = sample_df["title"].tolist()
    print(f"Embedding {len(titles)} sample titles...")
    emb_sample = embed_titles(titles)

    # Centroides
    print("Embedding seed centroids...")
    cat_names = []
    centroids = []
    for cat, seeds in SEEDS.items():
        emb_seeds = embed_titles(seeds)
        centroids.append(emb_seeds.mean(axis=0))
        cat_names.append(cat)
    centroids = np.stack(centroids)
    centroids = centroids / np.linalg.norm(centroids, axis=1, keepdims=True)

    # Cosine similarity (normalized)
    sims = emb_sample @ centroids.T  # (n_sample, n_cat)
    assignments = sims.argmax(axis=1)
    sample_df = sample_df.copy()
    sample_df["embedding_type"] = [cat_names[i] for i in assignments]
    return sample_df


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw/stackoverflow"))
    p.add_argument("--out-dir", type=Path, default=Path("outputs/tables"))
    p.add_argument("--n-sample", type=int, default=5000)
    args = p.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading stratified sample (n={args.n_sample}) from raw...")
    sample = load_sample_questions(args.raw_dir, n=args.n_sample, seed=SEED)
    print(f"Sample loaded: {len(sample)} questions")
    print(sample["heuristic_type"].value_counts())

    sample = classify_embedding(sample)

    # Binary substitutable
    sample["heuristic_sub"] = sample["heuristic_type"].isin(SUBSTITUTABLE).astype(int)
    sample["embedding_sub"] = sample["embedding_type"].isin(SUBSTITUTABLE).astype(int)

    # Cohen's kappa
    k_7way = kappa_cohen(sample["heuristic_type"], sample["embedding_type"])
    k_binary = kappa_cohen(sample["heuristic_sub"], sample["embedding_sub"])
    print(f"\nCohen's kappa (7-way): {k_7way:.3f}")
    print(f"Cohen's kappa (binary substitutable): {k_binary:.3f}")

    # Cross-tabulation
    ct = pd.crosstab(sample["heuristic_type"], sample["embedding_type"])
    print("\n=== Cross-tabulation ===")
    print(ct.to_string())

    # Save sample with both classifications
    sample.to_csv(args.out_dir / "rp_validation_question_type.csv", index=False)

    # Save kappa results
    pd.DataFrame([
        {"comparison": "heuristic_vs_embedding_7way", "kappa": k_7way, "n": len(sample)},
        {"comparison": "heuristic_vs_embedding_binary", "kappa": k_binary, "n": len(sample)},
    ]).to_csv(args.out_dir / "rp_validation_kappa.csv", index=False)
    print(f"\nsaved {args.out_dir / 'rp_validation_kappa.csv'}")
    print(f"saved {args.out_dir / 'rp_validation_question_type.csv'}")


if __name__ == "__main__":
    main()
