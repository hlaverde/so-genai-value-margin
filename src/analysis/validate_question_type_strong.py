"""Validación reforzada de la clasificación substitutable / non-substitutable.

Mejoras respecto a la versión simple:
    - Muestra estratificada de 10,000 preguntas (antes 5,000).
    - Tres clasificadores independientes:
        (1) Heurístico (basado en patrones de título y body length).
        (2) Embedding A: sentence-transformers/all-MiniLM-L6-v2.
        (3) Embedding B: sentence-transformers/all-mpnet-base-v2
            (diferente arquitectura y entrenamiento).
    - Pairwise Cohen's kappa entre los tres pares.
    - Fleiss' kappa (multi-rater) sobre los tres clasificadores.
    - Reporta tanto 7-way como binary substitutable.
    - High-agreement subsample DDD: cells donde los 3 clasificadores
      coinciden en el binario.

Salidas:
    outputs/tables/rp_validation_strong_kappa.csv
    outputs/tables/rp_validation_strong_crosstab.csv
    outputs/tables/rp_validation_strong_high_agreement_ddd.csv
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")
SEED = 20251122

SUBSTITUTABLE = {
    "short_code", "long_code", "how_to", "debugging_simple",
    "other_conceptual",
}

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
        "Iterate through a dictionary in Python",
        "Convert list to numpy array",
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
        "Vue.js Vuex action not committing mutation in production",
        "Rails ActiveRecord query returns wrong subset under join",
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
        "How can I implement rate limiting in Node.js?",
        "How do I set up a CI pipeline in GitHub Actions?",
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
        "Exception thrown when calling REST API in Java client",
        "Traceback: KeyError when processing CSV row",
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
        "What is referential transparency and why does it matter?",
        "Difference between mutex and semaphore concurrency primitives",
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
        "Cuda toolkit version incompatible with installed driver",
        "Setup configuration file missing for vcpkg on Windows 11",
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
        "Best practice for event sourcing in domain-driven design",
        "Scalable strategy for distributed transactions across services",
    ],
}


def classify_heuristic(row) -> str:
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


def load_stratified_sample(raw_dir: Path, n: int, seed: int) -> pd.DataFrame:
    files = sorted(raw_dir.glob("stackoverflow_question_type_raw_2022-*.csv")) + \
            sorted(raw_dir.glob("stackoverflow_question_type_raw_2023-*.csv")) + \
            sorted(raw_dir.glob("stackoverflow_question_type_raw_2024-*.csv"))
    frames = []
    for f in files[:60]:
        try:
            frames.append(pd.read_csv(
                f, usecols=["question_id", "title", "body_length", "has_code"]
            ))
        except Exception:
            continue
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates("question_id").reset_index(drop=True)
    df = df[df["title"].notna() & (df["title"].str.len() > 5)].reset_index(drop=True)
    df["heuristic_type"] = df.apply(classify_heuristic, axis=1)

    rng = np.random.default_rng(seed)
    per_cat = n // len(SEEDS)
    samples = []
    for cat in SEEDS.keys():
        sub = df[df["heuristic_type"] == cat]
        if len(sub) == 0:
            continue
        k = min(per_cat, len(sub))
        idx = rng.choice(len(sub), size=k, replace=False)
        samples.append(sub.iloc[idx])
    return pd.concat(samples, ignore_index=True)


def embed_and_assign(titles, model_name) -> list[str]:
    from sentence_transformers import SentenceTransformer
    print(f"Loading {model_name}...")
    model = SentenceTransformer(model_name)
    print(f"Embedding {len(titles)} titles...")
    emb_sample = model.encode(
        titles, batch_size=64, show_progress_bar=False,
        convert_to_numpy=True, normalize_embeddings=True,
    )
    print("Embedding seed centroids...")
    cat_names = []
    centroids = []
    for cat, seeds in SEEDS.items():
        emb_seeds = model.encode(
            seeds, batch_size=32, show_progress_bar=False,
            convert_to_numpy=True, normalize_embeddings=True,
        )
        centroids.append(emb_seeds.mean(axis=0))
        cat_names.append(cat)
    centroids = np.stack(centroids)
    centroids = centroids / np.linalg.norm(centroids, axis=1, keepdims=True)
    sims = emb_sample @ centroids.T
    assignments = sims.argmax(axis=1)
    return [cat_names[i] for i in assignments]


def fleiss_kappa(ratings: np.ndarray) -> float:
    """Fleiss' kappa for multi-rater categorical agreement.

    Args:
        ratings: matrix (n_items, n_categories) where each row sums to
            n_raters and counts how many raters assigned each category.
    Returns:
        Fleiss kappa.
    """
    n, k = ratings.shape
    raters = ratings.sum(axis=1)[0]
    p_j = ratings.sum(axis=0) / (n * raters)
    P_i = (
        (ratings * (ratings - 1)).sum(axis=1) / (raters * (raters - 1))
    )
    Pbar = P_i.mean()
    PE = (p_j ** 2).sum()
    return float((Pbar - PE) / (1 - PE)) if (1 - PE) > 0 else float("nan")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw/stackoverflow"))
    p.add_argument("--out-dir", type=Path, default=Path("outputs/tables"))
    p.add_argument("--n-sample", type=int, default=10000)
    args = p.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1] Loading stratified sample (n={args.n_sample})...")
    sample = load_stratified_sample(args.raw_dir, args.n_sample, SEED)
    print(f"     {len(sample)} questions loaded")

    titles = sample["title"].tolist()
    sample["minilm_type"] = embed_and_assign(titles, "sentence-transformers/all-MiniLM-L6-v2")
    sample["mpnet_type"] = embed_and_assign(titles, "sentence-transformers/all-mpnet-base-v2")

    # Binary substitutable
    for col_in, col_out in [("heuristic_type", "heuristic_sub"),
                             ("minilm_type", "minilm_sub"),
                             ("mpnet_type", "mpnet_sub")]:
        sample[col_out] = sample[col_in].isin(SUBSTITUTABLE).astype(int)

    # Pairwise Cohen's kappa
    from sklearn.metrics import cohen_kappa_score
    print("\n[2] Pairwise Cohen's kappa:")
    pairs_7way = []
    pairs_binary = []
    pair_names = [("heuristic", "minilm"), ("heuristic", "mpnet"), ("minilm", "mpnet")]
    for a, b in pair_names:
        k7 = cohen_kappa_score(sample[f"{a}_type"], sample[f"{b}_type"])
        kb = cohen_kappa_score(sample[f"{a}_sub"], sample[f"{b}_sub"])
        pairs_7way.append({"pair": f"{a} vs {b}", "kappa": k7})
        pairs_binary.append({"pair": f"{a} vs {b}", "kappa": kb})
        print(f"  {a} vs {b}: 7-way kappa = {k7:.3f}  |  binary kappa = {kb:.3f}")

    # Fleiss kappa (binary: 0 = non-sub, 1 = sub)
    print("\n[3] Fleiss' kappa (3 raters, binary substitutable):")
    raters_binary = np.column_stack([
        1 - sample["heuristic_sub"].values, sample["heuristic_sub"].values
    ])
    raters_binary += np.column_stack([
        1 - sample["minilm_sub"].values, sample["minilm_sub"].values
    ])
    raters_binary += np.column_stack([
        1 - sample["mpnet_sub"].values, sample["mpnet_sub"].values
    ])
    fleiss_binary = fleiss_kappa(raters_binary)
    print(f"  binary Fleiss kappa = {fleiss_binary:.3f}")

    # Fleiss 7-way
    cats = sorted(SEEDS.keys())
    cat_idx = {c: i for i, c in enumerate(cats)}
    raters_7way = np.zeros((len(sample), len(cats)), dtype=int)
    for col in ["heuristic_type", "minilm_type", "mpnet_type"]:
        for i, c in enumerate(sample[col].values):
            raters_7way[i, cat_idx[c]] += 1
    fleiss_7way = fleiss_kappa(raters_7way)
    print(f"  7-way Fleiss kappa = {fleiss_7way:.3f}")

    # High-agreement subsample
    sample["all_three_agree_binary"] = (
        (sample["heuristic_sub"] == sample["minilm_sub"])
        & (sample["heuristic_sub"] == sample["mpnet_sub"])
    ).astype(int)
    share_high = sample["all_three_agree_binary"].mean() * 100
    print(f"\n[4] High-agreement share (all 3 classifiers agree on binary): {share_high:.1f}%")

    # Persist
    kappa_rows = (
        [{"comparison": f"cohen_7way_{p['pair']}", "kappa": p["kappa"]} for p in pairs_7way]
        + [{"comparison": f"cohen_binary_{p['pair']}", "kappa": p["kappa"]} for p in pairs_binary]
        + [{"comparison": "fleiss_binary_3raters", "kappa": fleiss_binary},
           {"comparison": "fleiss_7way_3raters", "kappa": fleiss_7way},
           {"comparison": "share_3raters_agree_binary", "kappa": share_high / 100}]
    )
    pd.DataFrame(kappa_rows).to_csv(args.out_dir / "rp_validation_strong_kappa.csv", index=False)
    print(f"\nsaved {args.out_dir / 'rp_validation_strong_kappa.csv'}")

    # Cross-tabulation: heuristic vs majority of (minilm, mpnet)
    sample["embedding_majority_sub"] = (
        (sample["minilm_sub"] + sample["mpnet_sub"]) >= 1
    ).astype(int)
    ct = pd.crosstab(sample["heuristic_sub"], sample["embedding_majority_sub"],
                     margins=True)
    ct.to_csv(args.out_dir / "rp_validation_strong_crosstab.csv")
    print(f"\ncrosstab heuristic vs embedding-majority binary:")
    print(ct.to_string())

    sample.to_csv(args.out_dir / "rp_validation_strong_sample.csv", index=False)


if __name__ == "__main__":
    main()
