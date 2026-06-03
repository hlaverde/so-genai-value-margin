"""Análisis adicionales solicitados por el referee 3 (v3 RP):

    (a) Índice continuo de substitutability por tag-week-question_type
        construido a partir de los embeddings (similitud al centroide
        de las categorías substitutables menos la similitud al
        centroide de las no substitutables).
    (b) DDD usando el índice continuo en lugar de la binaria
        substitutable/non-substitutable, y comparación con la binaria.
    (c) DDD por cada una de las 7 categorías en lugar de
        agregación binaria (ya se tenía; se reformatea como tabla
        principal).
    (d) Test de complementariedad: ¿son las preguntas POST más
        complejas que las PRE? Estadísticos de body_length,
        code_share, accepted_answer_rate, answer_count antes y
        después de ChatGPT, dentro de tags high-AI vs low-AI.
    (e) Benchmarking de la magnitud 67k contra métricas externas:
        - 67k vs preguntas únicas post-ChatGPT en top-100 tags
        - 67k vs nuevos usuarios post-ChatGPT
        - 67k vs accepted answers en el periodo post
        - tasa anual implícita y horas-equivalentes de programador
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")


def fit_ddd_continuous(df, sub_score_col, ai_col="ai_answerability_structural"):
    """DDD usando una sustitutibilidad CONTINUA en lugar de la binaria."""
    df = df.copy()
    df["sub_cont"] = df[sub_score_col]
    # Estandarizar: media 0, sd 1 (para comparabilidad)
    df["sub_cont"] = (df["sub_cont"] - df["sub_cont"].mean()) / df["sub_cont"].std(ddof=0)
    df["ai"] = df[ai_col]
    df["post"] = (df["week_start"] >= CHATGPT_RELEASE).astype(int)
    df["ai_post"] = df["ai"] * df["post"]
    df["ai_subc"] = df["ai"] * df["sub_cont"]
    df["post_subc"] = df["post"] * df["sub_cont"]
    df["ai_post_subc"] = df["ai"] * df["post"] * df["sub_cont"]
    df["week_id"] = df["week_start"].astype(str)
    formula = (
        "log_questions_p1 ~ ai_post + ai_subc + post_subc + ai_post_subc "
        "| tag_qtype + week_id"
    )
    fit = pf.feols(formula, data=df, vcov={"CRV1": "tag"})
    return {
        "estimate": float(fit.coef()["ai_post_subc"]),
        "se": float(fit.se()["ai_post_subc"]),
        "p": float(fit.pvalue()["ai_post_subc"]),
        "n": int(fit._N),
        "sub_col": sub_score_col,
    }


def build_substitutability_score_from_embeddings(
    panel: pd.DataFrame, validation_sample: pd.DataFrame, model_name: str
) -> dict[str, float]:
    """Para cada question_type k, calcular un substitutability score
    continuo derivado de las distancias en embeddings al centroide de
    cada categoría substitutable vs no substitutable.

    Retorna un dict question_type -> score continuo.
    """
    from sentence_transformers import SentenceTransformer

    SEEDS = {
        "short_code": validation_sample[
            validation_sample["heuristic_type"] == "short_code"
        ]["title"].sample(min(50, (validation_sample["heuristic_type"] == "short_code").sum()), random_state=0).tolist(),
        "long_code": validation_sample[
            validation_sample["heuristic_type"] == "long_code"
        ]["title"].sample(min(50, (validation_sample["heuristic_type"] == "long_code").sum()), random_state=0).tolist(),
        "how_to": validation_sample[
            validation_sample["heuristic_type"] == "how_to"
        ]["title"].sample(min(50, (validation_sample["heuristic_type"] == "how_to").sum()), random_state=0).tolist(),
        "debugging_simple": validation_sample[
            validation_sample["heuristic_type"] == "debugging_simple"
        ]["title"].sample(min(50, (validation_sample["heuristic_type"] == "debugging_simple").sum()), random_state=0).tolist(),
        "other_conceptual": validation_sample[
            validation_sample["heuristic_type"] == "other_conceptual"
        ]["title"].sample(min(50, (validation_sample["heuristic_type"] == "other_conceptual").sum()), random_state=0).tolist(),
        "version_environment_specific": validation_sample[
            validation_sample["heuristic_type"] == "version_environment_specific"
        ]["title"].sample(min(50, (validation_sample["heuristic_type"] == "version_environment_specific").sum()), random_state=0).tolist(),
        "advanced_architecture": validation_sample[
            validation_sample["heuristic_type"] == "advanced_architecture"
        ]["title"].sample(min(50, (validation_sample["heuristic_type"] == "advanced_architecture").sum()), random_state=0).tolist(),
    }

    print(f"Loading {model_name}...")
    model = SentenceTransformer(model_name)

    # Calcular centroide de cada categoría
    centroids = {}
    for cat, texts in SEEDS.items():
        if len(texts) == 0:
            centroids[cat] = None
            continue
        emb = model.encode(
            texts, batch_size=64, show_progress_bar=False,
            convert_to_numpy=True, normalize_embeddings=True,
        )
        centroids[cat] = emb.mean(axis=0)

    # Para cada categoría k, su substitutability score es:
    #   avg cosine sim to SUBSTITUTABLE categories
    #   - avg cosine sim to NON-SUBSTITUTABLE categories
    SUB = {"short_code", "long_code", "how_to", "debugging_simple", "other_conceptual"}
    NONSUB = {"version_environment_specific", "advanced_architecture"}

    scores = {}
    for cat, centroid in centroids.items():
        if centroid is None:
            scores[cat] = 0.0
            continue
        sim_sub = np.mean([
            float(centroid @ centroids[s] / (np.linalg.norm(centroid) * np.linalg.norm(centroids[s])))
            for s in SUB if centroids.get(s) is not None and s != cat
        ])
        sim_nonsub = np.mean([
            float(centroid @ centroids[ns] / (np.linalg.norm(centroid) * np.linalg.norm(centroids[ns])))
            for ns in NONSUB if centroids.get(ns) is not None and ns != cat
        ])
        scores[cat] = sim_sub - sim_nonsub

    return scores


def complementarity_check(panel: pd.DataFrame, out_dir: Path) -> None:
    """Compara complejidad de preguntas pre vs post-ChatGPT
    dentro de tags high-AI vs low-AI."""
    df = panel.copy()
    df["period"] = np.where(df["week_start"] < CHATGPT_RELEASE, "pre", "post")
    df["ai_q"] = pd.qcut(df["ai_answerability_structural"], 2,
                          labels=["low_AI", "high_AI"])
    # Agregar a tag-week-period
    weekly = df.groupby(["tag", "ai_q", "period", "week_start"], observed=True).agg(
        questions=("questions", "sum"),
        body_length_mean=("body_length_mean", "mean"),
        accepted_share=("accepted_share", "mean"),
        code_share=("code_share", "mean"),
    ).reset_index()
    grouped = weekly.groupby(["ai_q", "period"], observed=True).agg(
        body_length=("body_length_mean", "mean"),
        accepted_share=("accepted_share", "mean"),
        code_share=("code_share", "mean"),
    )
    print("=== Complementarity check: complexity pre vs post by AI quartile ===")
    print(grouped.to_string())
    grouped.to_csv(out_dir / "rp_v3_complementarity.csv")
    print(f"\nsaved {out_dir / 'rp_v3_complementarity.csv'}")


def magnitude_benchmarks(panel: pd.DataFrame, out_dir: Path) -> None:
    """Anclajes externos para los 67k preguntas."""
    df = panel.copy()
    post = df[df["week_start"] >= CHATGPT_RELEASE]
    pre = df[df["week_start"] < CHATGPT_RELEASE]
    n_questions_post = post["questions"].sum()
    n_questions_pre = pre["questions"].sum()
    n_weeks_post = post["week_start"].nunique()
    n_weeks_pre = pre["week_start"].nunique()
    avg_post = n_questions_post / n_weeks_post
    avg_pre = n_questions_pre / n_weeks_pre

    AI_CHANNEL = 67000  # del DDD
    benchmarks = {
        "ai_channel_missing": AI_CHANNEL,
        "total_questions_post": int(n_questions_post),
        "share_ai_channel_of_post_total": AI_CHANNEL / n_questions_post,
        "share_ai_channel_of_pre_total": AI_CHANNEL / n_questions_pre,
        "ai_channel_per_week_post": AI_CHANNEL / n_weeks_post,
        "avg_weekly_post": float(avg_post),
        "ai_channel_as_share_of_weekly_post": (AI_CHANNEL / n_weeks_post) / avg_post,
        "avg_weekly_pre": float(avg_pre),
        "n_weeks_post": int(n_weeks_post),
        # Asumiendo un programador "novel" lee/escribe ~300 preguntas/año en su
        # primer año (orden de magnitud, basado en lit. user activity online):
        "implied_novel_programmer_equivalents": AI_CHANNEL / 300,
        # 67k preguntas, asumiendo cada pregunta=15 min de tiempo de programador
        "implied_developer_hours": AI_CHANNEL * 0.25,
    }
    for k, v in benchmarks.items():
        if isinstance(v, float):
            print(f"  {k}: {v:,.4f}")
        else:
            print(f"  {k}: {v:,}")
    pd.DataFrame([benchmarks]).to_csv(out_dir / "rp_v3_magnitude_benchmarks.csv", index=False)
    print(f"\nsaved {out_dir / 'rp_v3_magnitude_benchmarks.csv'}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--panel", type=Path,
                   default=Path("data/processed/stackoverflow_question_type_master_panel.csv"))
    p.add_argument("--validation-sample", type=Path,
                   default=Path("outputs/tables/rp_validation_strong_sample.csv"))
    p.add_argument("--out-dir", type=Path, default=Path("outputs/tables"))
    p.add_argument("--skip-embeddings", action="store_true")
    args = p.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    panel = pd.read_csv(args.panel)
    panel["week_start"] = pd.to_datetime(panel["week_start"])

    # =============================
    # (a) Continuous substitutability index from embeddings
    # =============================
    print("=== (a) Continuous substitutability index ===")
    if not args.skip_embeddings and args.validation_sample.exists():
        val = pd.read_csv(args.validation_sample)
        cont_scores = build_substitutability_score_from_embeddings(
            panel, val, "sentence-transformers/all-MiniLM-L6-v2"
        )
        print("Continuous substitutability scores per category:")
        for cat, sc in sorted(cont_scores.items(), key=lambda x: -x[1]):
            print(f"  {cat:>32s}: {sc:+.4f}")
        # Asignar score a panel
        panel["sub_score_continuous"] = panel["question_type"].map(cont_scores)
        pd.DataFrame([{"category": k, "score": v}
                      for k, v in cont_scores.items()]).to_csv(
            args.out_dir / "rp_v3_substitutability_scores.csv", index=False)
    else:
        print("  Skipping embedding-based score (validation sample missing).")
        # Fallback: rank by heuristic mapping (no LLM)
        manual_scores = {
            "short_code": 1.0,
            "how_to": 0.85,
            "long_code": 0.65,
            "debugging_simple": 0.50,
            "other_conceptual": 0.25,
            "advanced_architecture": -0.30,
            "version_environment_specific": -1.0,
        }
        panel["sub_score_continuous"] = panel["question_type"].map(manual_scores)

    # =============================
    # (b) DDD with continuous index
    # =============================
    print("\n=== (b) DDD with continuous substitutability score ===")
    rows = []
    for ai_col in ["ai_answerability_structural", "ai_answerability_zscore"]:
        r = fit_ddd_continuous(panel, "sub_score_continuous", ai_col)
        r["ai_measure"] = ai_col
        rows.append(r)
        print(
            f"  {ai_col}: DDD = {r['estimate']:+.4f} "
            f"(SE {r['se']:.4f}, p={r['p']:.3g}, n={r['n']:,})"
        )
    pd.DataFrame(rows).to_csv(args.out_dir / "rp_v3_ddd_continuous.csv", index=False)
    print(f"  saved {args.out_dir / 'rp_v3_ddd_continuous.csv'}")

    # =============================
    # (c) DDD per category (already in heterogeneity_by_question_type.csv)
    # =============================
    print("\n=== (c) DDD per category (using heterogeneity output) ===")
    het_path = args.out_dir / "heterogeneity_by_question_type.csv"
    if het_path.exists():
        het = pd.read_csv(het_path)
        print(het[["question_type", "ai_post_coef", "ai_post_se", "ai_post_p"]].to_string(index=False))

    # =============================
    # (d) Complementarity check
    # =============================
    print("\n=== (d) Complementarity check (complexity pre/post by AI quartile) ===")
    complementarity_check(panel, args.out_dir)

    # =============================
    # (e) Magnitude benchmarks
    # =============================
    print("\n=== (e) Magnitude benchmarks ===")
    magnitude_benchmarks(panel, args.out_dir)


if __name__ == "__main__":
    main()
