"""Triple diferencia (DDD) AI_answerability × Post-ChatGPT × Substitutable.

Modelo base, en notación de Sun & Abraham:

    log(1 + Q_{t,w,k}) =
        β_DDD · (AI_t · Post_w · Sub_k)
      + γ_1 (AI_t · Post_w) + γ_2 (AI_t · Sub_k) + γ_3 (Post_w · Sub_k)
      + α_{t,k} (tag-question_type FE)
      + δ_w     (week FE)
      + ε_{t,w,k}

Donde:
    t = tag (100)
    w = week (~261)
    k = question_type (7)
    Sub_k = 1 si k ∈ {short_code, long_code, how_to, debugging_simple, other_conceptual}
    Post_w = 1 si w >= 2022-11-30
    AI_t   = ai_answerability_zscore (continuo, std=0.519)
    Q_{t,w,k} = preguntas

Errores estándar: clustered por tag (CR1).

Especificaciones:
    1. OLS con log(1+Q) (interpretación: semi-elasticidad cuando Q es grande).
    2. PPML (Poisson GLM con log-link) sobre Q raw (robusto a ceros y heterocedasticidad,
       siguiendo Santos Silva & Tenreyro 2006). Implementado con pyhdfe para absorber FE
       de alta dimensionalidad cuando el solver lo permite.
    3. Variantes con las 4 medidas de answerability (zscore, pca, quantile, structural).
    4. Subsamples top-50 y top-100 tags por questions_pre.
    5. Outcome alternativos: log_unique_users_p1, accepted_per_q.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.formula.api import ols


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")
ANSWERABILITY_COLS = [
    "ai_answerability_zscore",
    "ai_answerability_pca",
    "ai_answerability_quantile",
    "ai_answerability_structural",
]


@dataclass
class DDDSpec:
    name: str
    answerability_col: str
    outcome: str  # column name in panel
    sample: str = "full"  # full, top50, top100
    family: str = "ols_log1p"  # ols_log1p, ppml


def load_panel(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    return df


def restrict_sample(df: pd.DataFrame, sample: str) -> pd.DataFrame:
    if sample == "full":
        return df.copy()
    # Rank tags by questions_pre, take top-N
    n = int(sample.replace("top", ""))
    pre_rank = (
        df.groupby("tag")["questions_pre"].first().sort_values(ascending=False)
    )
    top_tags = pre_rank.head(n).index.tolist()
    out = df[df["tag"].isin(top_tags)].reset_index(drop=True)
    return out


def fit_ols_log1p(
    df: pd.DataFrame,
    outcome: str,
    ai_col: str,
    cluster_col: str = "tag",
) -> dict:
    """OLS with manual FE via formula. FE absorbed by C(tag_qtype) + C(week_start).

    Cluster-robust SE on `cluster_col`.
    """
    df = df.copy()
    df = df.rename(columns={ai_col: "ai"})
    df = df.rename(columns={outcome: "y"})
    df["sub"] = df["substitutable_type"].astype(int)
    df["post"] = df["post_chatgpt"].astype(int)
    df["ai_post"] = df["ai"] * df["post"]
    df["ai_sub"] = df["ai"] * df["sub"]
    df["post_sub"] = df["post"] * df["sub"]
    df["ai_post_sub"] = df["ai"] * df["post"] * df["sub"]

    formula = (
        "y ~ ai_post + ai_sub + post_sub + ai_post_sub "
        "+ C(tag_qtype) + C(week_start)"
    )
    model = ols(formula, data=df).fit(
        cov_type="cluster", cov_kwds={"groups": df[cluster_col]}
    )
    return {
        "model": model,
        "params": model.params.loc[["ai_post", "ai_sub", "post_sub", "ai_post_sub"]],
        "se": model.bse.loc[["ai_post", "ai_sub", "post_sub", "ai_post_sub"]],
        "tvalues": model.tvalues.loc[["ai_post", "ai_sub", "post_sub", "ai_post_sub"]],
        "pvalues": model.pvalues.loc[["ai_post", "ai_sub", "post_sub", "ai_post_sub"]],
        "nobs": int(model.nobs),
        "rsquared": float(model.rsquared),
        "rsquared_adj": float(model.rsquared_adj),
        "df_resid": int(model.df_resid),
    }


def fit_ppml(
    df: pd.DataFrame,
    outcome: str,
    ai_col: str,
    cluster_col: str = "tag",
) -> dict:
    """Pseudo-Poisson Maximum Likelihood con FE alta dimensionalidad (pyfixest).

    Sigue Santos Silva & Tenreyro (2006). Cluster-robust SE en `cluster_col`.
    """
    import pyfixest as pf

    df = df.copy()
    df = df.rename(columns={ai_col: "ai"})
    df = df.rename(columns={outcome: "y"})
    df["sub"] = df["substitutable_type"].astype(int)
    df["post"] = df["post_chatgpt"].astype(int)
    df["ai_post"] = df["ai"] * df["post"]
    df["ai_sub"] = df["ai"] * df["sub"]
    df["post_sub"] = df["post"] * df["sub"]
    df["ai_post_sub"] = df["ai"] * df["post"] * df["sub"]
    # pyfixest requiere week_start como categórico/serializable
    df["week_id"] = df["week_start"].astype(str)

    # ai_sub está absorbido por FE tag_qtype (ai y sub son constantes within tag_qtype).
    # post_sub también está absorbido por FE de week (sub es constante within week
    # cuando consideramos las distintas weeks por separado — esto solo aplica si
    # hay variación; en la práctica no se absorbe). Mantenemos post_sub si existe.
    fit = pf.fepois(
        "y ~ ai_post + post_sub + ai_post_sub | tag_qtype + week_id",
        data=df,
        vcov={"CRV1": cluster_col},
    )
    coef = fit.coef()
    se = fit.se()
    tvals = fit.tstat()
    pvals = fit.pvalue()
    available = set(coef.index)
    keep = [k for k in ["ai_post", "ai_sub", "post_sub", "ai_post_sub"] if k in available]
    def _get(series, k):
        return float(series[k]) if k in series.index else float("nan")
    return {
        "model": fit,
        "params": pd.Series({k: _get(coef, k) for k in ["ai_post", "ai_sub", "post_sub", "ai_post_sub"]}),
        "se": pd.Series({k: _get(se, k) for k in ["ai_post", "ai_sub", "post_sub", "ai_post_sub"]}),
        "tvalues": pd.Series({k: _get(tvals, k) for k in ["ai_post", "ai_sub", "post_sub", "ai_post_sub"]}),
        "pvalues": pd.Series({k: _get(pvals, k) for k in ["ai_post", "ai_sub", "post_sub", "ai_post_sub"]}),
        "nobs": int(fit._N),
        "deviance": float("nan"),
        "llf": float("nan"),
        "df_resid": int(fit._N - len(fit._coefnames)),
    }


def summarize_spec(name: str, result: dict, spec: DDDSpec) -> pd.DataFrame:
    rows = []
    for k in ["ai_post", "ai_sub", "post_sub", "ai_post_sub"]:
        rows.append(
            {
                "spec": name,
                "answerability": spec.answerability_col,
                "outcome": spec.outcome,
                "sample": spec.sample,
                "family": spec.family,
                "coef_name": k,
                "estimate": float(result["params"][k]),
                "std_err": float(result["se"][k]),
                "t": float(result["tvalues"][k]),
                "p": float(result["pvalues"][k]),
                "nobs": result["nobs"],
            }
        )
    return pd.DataFrame(rows)


def run_all(panel: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = [
        # Especificación principal
        DDDSpec(
            name="main_ols_log1p_zscore_full",
            answerability_col="ai_answerability_zscore",
            outcome="log_questions_p1",
            sample="full",
            family="ols_log1p",
        ),
        # Robustez por medida de answerability
        DDDSpec(
            name="alt_ols_log1p_pca_full",
            answerability_col="ai_answerability_pca",
            outcome="log_questions_p1",
            sample="full",
            family="ols_log1p",
        ),
        DDDSpec(
            name="alt_ols_log1p_quantile_full",
            answerability_col="ai_answerability_quantile",
            outcome="log_questions_p1",
            sample="full",
            family="ols_log1p",
        ),
        DDDSpec(
            name="alt_ols_log1p_structural_full",
            answerability_col="ai_answerability_structural",
            outcome="log_questions_p1",
            sample="full",
            family="ols_log1p",
        ),
        # Robustez por subsample
        DDDSpec(
            name="sub_ols_log1p_zscore_top50",
            answerability_col="ai_answerability_zscore",
            outcome="log_questions_p1",
            sample="top50",
            family="ols_log1p",
        ),
        # Robustez de outcome
        DDDSpec(
            name="alt_ols_log1p_zscore_users",
            answerability_col="ai_answerability_zscore",
            outcome="log_unique_users_p1",
            sample="full",
            family="ols_log1p",
        ),
        # PPML principal (counts directos)
        DDDSpec(
            name="ppml_zscore_full",
            answerability_col="ai_answerability_zscore",
            outcome="questions",
            sample="full",
            family="ppml",
        ),
    ]

    all_rows = []
    for spec in specs:
        df = restrict_sample(panel, spec.sample)
        print(f"[{spec.name}] sample rows={len(df)} family={spec.family}")
        try:
            if spec.family == "ols_log1p":
                res = fit_ols_log1p(df, spec.outcome, spec.answerability_col)
            elif spec.family == "ppml":
                res = fit_ppml(df, spec.outcome, spec.answerability_col)
            else:
                raise ValueError(spec.family)
        except Exception as exc:
            print(f"  FAILED: {exc}")
            continue
        rows = summarize_spec(spec.name, res, spec)
        all_rows.append(rows)
        # Imprime solo el DDD
        ddd = rows[rows["coef_name"] == "ai_post_sub"].iloc[0]
        print(
            f"  DDD = {ddd['estimate']:+.4f} (SE {ddd['std_err']:.4f}, p={ddd['p']:.3g})"
        )

    out = pd.concat(all_rows, ignore_index=True)
    out_csv = out_dir / "ddd_question_type_main.csv"
    out.to_csv(out_csv, index=False)
    print(f"\nGuardado: {out_csv}")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--panel",
        type=Path,
        default=Path("data/processed/stackoverflow_question_type_master_panel.csv"),
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("outputs/tables"),
    )
    args = p.parse_args()
    panel = load_panel(args.panel)
    run_all(panel, args.out_dir)


if __name__ == "__main__":
    main()
