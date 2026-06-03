"""DDD descomposición por cada uno de los 7 question_types.

Modelo (para cada question_type k separadamente):
    log(1 + Q_{t,w,k}) = β_k · (AI_t · Post_w) + α_t + δ_w + ε

donde k es uno de los 7 tipos. Tags FE absorben heterogeneidad permanente
por tag. Esto da un coeficiente "Δ relativo por SD de AI dentro del tipo".
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf


CHATGPT_RELEASE = pd.Timestamp("2022-11-30")

QTYPE_ORDER = [
    "short_code", "how_to", "long_code", "debugging_simple", "other_conceptual",
    "version_environment_specific", "advanced_architecture",
]


def run(panel_path: Path, out_csv: Path, ai_col: str) -> None:
    df = pd.read_csv(panel_path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["ai"] = df[ai_col]
    df["post"] = (df["week_start"] >= CHATGPT_RELEASE).astype(int)
    df["ai_post"] = df["ai"] * df["post"]
    df["week_id"] = df["week_start"].astype(str)

    rows = []
    for qt in QTYPE_ORDER:
        sub = df[df["question_type"] == qt].copy()
        if len(sub) == 0:
            continue
        formula = "log_questions_p1 ~ ai_post | tag + week_id"
        fit = pf.feols(formula, data=sub, vcov={"CRV1": "tag"})
        coef = float(fit.coef()["ai_post"])
        se = float(fit.se()["ai_post"])
        p = float(fit.pvalue()["ai_post"])
        ci_lo = float(fit.confint().loc["ai_post", "2.5%"])
        ci_hi = float(fit.confint().loc["ai_post", "97.5%"])
        rows.append(
            {
                "question_type": qt,
                "n": int(fit._N),
                "n_tags": sub["tag"].nunique(),
                "n_weeks": sub["week_start"].nunique(),
                "ai_post_coef": coef,
                "ai_post_se": se,
                "ai_post_p": p,
                "ci_lo": ci_lo,
                "ci_hi": ci_hi,
                "is_substitutable": int(sub["substitutable_type"].iloc[0]),
            }
        )
        sub_flag = "sub" if rows[-1]["is_substitutable"] == 1 else "non-sub"
        print(
            f"  {qt:>32s} [{sub_flag:>7}] coef={coef:+.4f} "
            f"(SE {se:.4f}, p={p:.3g}, n={fit._N})"
        )

    out = pd.DataFrame(rows)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)
    print(f"\nsaved {out_csv}")

    # Figura
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 5))
    y_pos = np.arange(len(out))
    colors = ["#DD8452" if x == 1 else "#4C72B0" for x in out["is_substitutable"]]
    ax.errorbar(
        out["ai_post_coef"], y_pos,
        xerr=1.96 * out["ai_post_se"],
        fmt="o", color="black", ecolor="grey",
    )
    for i, (xv, c) in enumerate(zip(out["ai_post_coef"], colors)):
        ax.plot(xv, i, marker="o", markersize=10, color=c)
    ax.axvline(0, color="grey", linestyle="--", alpha=0.7)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(out["question_type"])
    ax.set_xlabel("DDD coefficient (AI × Post)")
    ax.set_title("Effect by question type (orange = substitutable, blue = non-substitutable)")
    ax.invert_yaxis()
    fig.tight_layout()
    fig_path = out_csv.parent.parent / "figures" / "heterogeneity_by_question_type.png"
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(fig_path, dpi=160)
    plt.close(fig)
    print(f"saved figure {fig_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--panel",
        type=Path,
        default=Path("data/processed/stackoverflow_question_type_master_panel.csv"),
    )
    p.add_argument(
        "--out-csv",
        type=Path,
        default=Path("outputs/tables/heterogeneity_by_question_type.csv"),
    )
    p.add_argument("--answerability", default="ai_answerability_zscore")
    args = p.parse_args()
    run(args.panel, args.out_csv, args.answerability)
