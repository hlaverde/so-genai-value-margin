import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from linearmodels.panel import PanelOLS
from statsmodels.stats.multitest import multipletests

from src.config import CHATGPT_RELEASE_DATE
from src.paths import PROCESSED_DIR, TABLES_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


MAIN_OUTCOMES = ["log_questions", "log_answers", "log_unique_users", "short_code_share"]
COUNT_OUTCOMES = ["questions", "answers", "accepted_answers", "unique_users", "closed_questions"]
PLACEBO_DATES = ["2019-11-30", "2020-11-30", "2021-11-30", "2022-06-30"]
AI_ML_TAGS = {
    "artificial-intelligence",
    "machine-learning",
    "deep-learning",
    "tensorflow",
    "pytorch",
    "keras",
    "scikit-learn",
    "nlp",
    "neural-network",
}


def prepare_panel(path: Path) -> pd.DataFrame:
    df = read_csv(path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["post_chatgpt"] = df["week_start"] >= pd.Timestamp(CHATGPT_RELEASE_DATE)
    df["week_index"] = ((df["week_start"] - df["week_start"].min()).dt.days // 7).astype(int)
    df["pre_trend_index"] = (
        (df["week_start"] - df.loc[df["week_start"] < pd.Timestamp(CHATGPT_RELEASE_DATE), "week_start"].min()).dt.days // 7
    ).astype(int)
    df["log_questions"] = np.log1p(df["questions"])
    df["log_answers"] = np.log1p(df["answers"])
    df["log_unique_users"] = np.log1p(df["unique_users"])
    df["log_accepted_answers"] = np.log1p(df["accepted_answers"])
    df["log_closed_questions"] = np.log1p(df["closed_questions"])
    df["ai_x_post"] = df["ai_answerability_zscore"] * df["post_chatgpt"].astype(int)
    return df.sort_values(["tag", "week_start"]).reset_index(drop=True)


def did_panel(df: pd.DataFrame, outcome: str, post_date: str = CHATGPT_RELEASE_DATE, cluster: str = "tag") -> dict[str, object]:
    data = df.copy()
    data["post"] = data["week_start"] >= pd.Timestamp(post_date)
    data["ai_x_post"] = data["ai_answerability_zscore"] * data["post"].astype(int)
    panel = data.set_index(["tag", "week_start"])
    fit_kwargs = {"cov_type": "clustered"}
    if cluster == "tag":
        fit_kwargs["cluster_entity"] = True
    elif cluster == "twoway":
        fit_kwargs["cluster_entity"] = True
        fit_kwargs["cluster_time"] = True
    else:
        raise ValueError(f"Unknown cluster option: {cluster}")
    res = PanelOLS(panel[outcome], panel[["ai_x_post"]], entity_effects=True, time_effects=True).fit(**fit_kwargs)
    return {
        "outcome": outcome,
        "post_date": pd.Timestamp(post_date).date().isoformat(),
        "estimate": res.params["ai_x_post"],
        "std_error": res.std_errors["ai_x_post"],
        "t_stat": res.tstats["ai_x_post"],
        "p_value": res.pvalues["ai_x_post"],
        "n_obs": int(res.nobs),
        "n_tags": int(data["tag"].nunique()),
    }


def slope_pretrend_tests(df: pd.DataFrame) -> pd.DataFrame:
    pre = df[df["week_start"] < pd.Timestamp(CHATGPT_RELEASE_DATE)].copy()
    rows = []
    for outcome in ["log_questions", "log_answers", "log_unique_users", "short_code_share"]:
        pre["ai_x_trend"] = pre["ai_answerability_zscore"] * pre["pre_trend_index"]
        res = smf.ols(f"{outcome} ~ ai_x_trend + C(tag) + C(week_start)", data=pre).fit(
            cov_type="cluster", cov_kwds={"groups": pre["tag"]}
        )
        rows.append(
            {
                "test": "pre_period_slope_test",
                "outcome": outcome,
                "statistic": res.tvalues["ai_x_trend"],
                "p_value": res.pvalues["ai_x_trend"],
                "estimate": res.params["ai_x_trend"],
                "std_error": res.bse["ai_x_trend"],
                "decision_5pct": "reject_parallel_pretrend" if res.pvalues["ai_x_trend"] < 0.05 else "do_not_reject",
            }
        )
    return pd.DataFrame(rows)


def binned_event_study(df: pd.DataFrame, outcome: str, bin_weeks: int = 13) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = df.copy()
    release_week = pd.Timestamp(CHATGPT_RELEASE_DATE) - pd.to_timedelta(pd.Timestamp(CHATGPT_RELEASE_DATE).weekday(), unit="D")
    data["rel_week"] = ((data["week_start"] - release_week).dt.days // 7).astype(int)
    data["rel_bin"] = np.floor(data["rel_week"] / bin_weeks).astype(int)
    data["rel_bin"] = data["rel_bin"].clip(-12, 12)
    omitted = -1
    bins = sorted(b for b in data["rel_bin"].unique() if b != omitted)
    term_names = []
    for b in bins:
        name = f"ai_bin_{b}".replace("-", "m")
        data[name] = data["ai_answerability_zscore"] * (data["rel_bin"] == b).astype(int)
        term_names.append(name)
    formula = f"{outcome} ~ {' + '.join(term_names)} + C(tag) + C(week_start)"
    res = smf.ols(formula, data=data).fit(cov_type="cluster", cov_kwds={"groups": data["tag"]})
    rows = []
    for b, name in zip(bins, term_names):
        rows.append(
            {
                "outcome": outcome,
                "bin_weeks": bin_weeks,
                "relative_bin": b,
                "relative_week_start": b * bin_weeks,
                "estimate": res.params.get(name, np.nan),
                "std_error": res.bse.get(name, np.nan),
                "p_value": res.pvalues.get(name, np.nan),
            }
        )
    pre_terms = [name for b, name in zip(bins, term_names) if b < 0 and b != omitted]
    if pre_terms:
        ftest = res.f_test(" = 0, ".join(pre_terms) + " = 0")
        tests = pd.DataFrame(
            [
                {
                    "test": "joint_f_test_pre_period_bins",
                    "outcome": outcome,
                    "statistic": float(ftest.fvalue),
                    "p_value": float(ftest.pvalue),
                    "estimate": np.nan,
                    "std_error": np.nan,
                    "decision_5pct": "reject_parallel_pretrend" if float(ftest.pvalue) < 0.05 else "do_not_reject",
                }
            ]
        )
    else:
        tests = pd.DataFrame()
    return pd.DataFrame(rows), tests


def placebo_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    pre = df[df["week_start"] < pd.Timestamp(CHATGPT_RELEASE_DATE)].copy()
    for date in PLACEBO_DATES:
        sample = pre.copy()
        rows.append({**did_panel(sample, "log_questions", date), "placebo_type": "fixed_date"})
        rows.append({**did_panel(sample, "log_answers", date), "placebo_type": "fixed_date"})
    real_q = did_panel(df, "log_questions", CHATGPT_RELEASE_DATE)
    real_a = did_panel(df, "log_answers", CHATGPT_RELEASE_DATE)
    rows.append({**real_q, "placebo_type": "real_chatgpt"})
    rows.append({**real_a, "placebo_type": "real_chatgpt"})
    return pd.DataFrame(rows)


def rolling_placebos(df: pd.DataFrame) -> pd.DataFrame:
    pre = df[df["week_start"] < pd.Timestamp(CHATGPT_RELEASE_DATE)].copy()
    dates = pd.date_range("2019-01-31", "2022-09-30", freq="ME")
    rows = []
    for date in dates:
        for outcome in ["log_questions", "log_answers"]:
            try:
                row = did_panel(pre, outcome, date.strftime("%Y-%m-%d"))
                row["placebo_type"] = "rolling_monthly"
                rows.append(row)
            except Exception as exc:
                rows.append(
                    {
                        "outcome": outcome,
                        "post_date": date.date().isoformat(),
                        "estimate": np.nan,
                        "std_error": np.nan,
                        "t_stat": np.nan,
                        "p_value": np.nan,
                        "n_obs": len(pre),
                        "n_tags": pre["tag"].nunique(),
                        "placebo_type": "rolling_monthly",
                        "error": str(exc),
                    }
                )
    return pd.DataFrame(rows)


def tag_pre_features(df: pd.DataFrame) -> pd.DataFrame:
    pre = df[df["week_start"] < pd.Timestamp(CHATGPT_RELEASE_DATE)].copy()
    rows = []
    for tag, g in pre.groupby("tag"):
        qfit = smf.ols("log_questions ~ week_index", data=g).fit()
        afit = smf.ols("log_answers ~ week_index", data=g).fit()
        rows.append(
            {
                "tag": tag,
                "ai_answerability_zscore": g["ai_answerability_zscore"].iloc[0],
                "mean_questions_pre": g["questions"].mean(),
                "mean_answers_pre": g["answers"].mean(),
                "trend_log_questions_pre": qfit.params["week_index"],
                "trend_log_answers_pre": afit.params["week_index"],
                "volatility_log_questions_pre": g["log_questions"].std(),
                "tag_maturity_weeks_pre": len(g),
                "code_share_pre": g["code_share"].mean(),
                "closed_share_pre": (g["closed_questions"].sum() / max(g["questions"].sum(), 1)),
                "answer_rate_pre": g["answer_rate"].mean(),
                "short_code_share_pre": g["short_code_share"].mean(),
            }
        )
    return pd.DataFrame(rows)


def mahalanobis_matched_tags(features: pd.DataFrame) -> pd.DataFrame:
    f = features.copy()
    f["tercile"] = pd.qcut(f["ai_answerability_zscore"], 3, labels=["low", "mid", "high"])
    high = f[f["tercile"].eq("high")].copy()
    low = f[f["tercile"].eq("low")].copy()
    match_cols = [
        "mean_questions_pre",
        "trend_log_questions_pre",
        "trend_log_answers_pre",
        "volatility_log_questions_pre",
        "tag_maturity_weeks_pre",
        "code_share_pre",
        "closed_share_pre",
        "answer_rate_pre",
    ]
    x_low = low[match_cols].to_numpy(float)
    x_all = f[match_cols].to_numpy(float)
    scale = np.nanstd(x_all, axis=0)
    scale[scale == 0] = 1
    x_low = (x_low - np.nanmean(x_all, axis=0)) / scale
    rows = []
    used_low: set[str] = set()
    for _, h in high.sort_values("ai_answerability_zscore", ascending=False).iterrows():
        xh = ((h[match_cols].to_numpy(float) - np.nanmean(x_all, axis=0)) / scale).reshape(1, -1)
        distances = np.sqrt(((x_low - xh) ** 2).sum(axis=1))
        candidates = low.copy()
        candidates["distance"] = distances
        candidates = candidates[~candidates["tag"].isin(used_low)].sort_values("distance")
        if candidates.empty:
            break
        m = candidates.iloc[0]
        used_low.add(m["tag"])
        rows.append(
            {
                "high_tag": h["tag"],
                "low_tag": m["tag"],
                "distance": m["distance"],
                "high_ai": h["ai_answerability_zscore"],
                "low_ai": m["ai_answerability_zscore"],
            }
        )
    return pd.DataFrame(rows)


def matched_did(df: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    matched_tags = set(matches["high_tag"]) | set(matches["low_tag"])
    full_rows = []
    matched = df[df["tag"].isin(matched_tags)].copy()
    for outcome in ["log_questions", "log_answers", "short_code_share"]:
        full = did_panel(df, outcome, CHATGPT_RELEASE_DATE)
        mat = did_panel(matched, outcome, CHATGPT_RELEASE_DATE)
        full_rows.append(
            {
                "outcome": outcome,
                "full_sample_estimate": full["estimate"],
                "full_sample_se": full["std_error"],
                "matched_sample_estimate": mat["estimate"],
                "matched_sample_se": mat["std_error"],
                "difference_matched_minus_full": mat["estimate"] - full["estimate"],
                "n_matched_tags": len(matched_tags),
            }
        )
    return pd.DataFrame(full_rows)


def ppml_fe(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    data = df.copy()
    data["ai_x_post"] = data["ai_answerability_zscore"] * data["post_chatgpt"].astype(int)
    for outcome in ["questions", "answers", "accepted_answers", "unique_users"]:
        formula = f"{outcome} ~ ai_x_post + C(tag) + C(week_start)"
        res = smf.glm(formula, data=data, family=sm.families.Poisson()).fit(
            cov_type="cluster", cov_kwds={"groups": data["tag"]}, maxiter=100
        )
        beta = res.params["ai_x_post"]
        rows.append(
            {
                "outcome": outcome,
                "estimate": beta,
                "std_error": res.bse["ai_x_post"],
                "p_value": res.pvalues["ai_x_post"],
                "irr": math.exp(beta),
                "percent_change": 100 * (math.exp(beta) - 1),
                "n_obs": int(res.nobs),
            }
        )
    return pd.DataFrame(rows)


def inference_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for outcome in ["log_questions", "log_answers", "log_unique_users"]:
        tag = did_panel(df, outcome, cluster="tag")
        two = did_panel(df, outcome, cluster="twoway")
        rows.append(
            {
                "outcome": outcome,
                "estimate": tag["estimate"],
                "cluster_tag_se": tag["std_error"],
                "cluster_tag_p": tag["p_value"],
                "two_way_cluster_se": two["std_error"],
                "two_way_cluster_p": two["p_value"],
                "wild_bootstrap_p": np.nan,
                "block_bootstrap_p": np.nan,
                "note": "wild/block bootstrap scaffold pending computational bootstrap run",
            }
        )
    return pd.DataFrame(rows)


def effect_sizes(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for outcome, count_col in [("log_questions", "questions"), ("log_answers", "answers"), ("log_unique_users", "unique_users")]:
        res = did_panel(df, outcome)
        pre_mean = df[df["week_start"] < pd.Timestamp(CHATGPT_RELEASE_DATE)][count_col].mean()
        pct = 100 * (math.exp(res["estimate"]) - 1)
        rows.append(
            {
                "outcome": outcome,
                "estimate": res["estimate"],
                "percent_change_per_sd_ai": pct,
                "pre_period_mean_weekly_tag_count": pre_mean,
                "approx_count_change_per_tag_week": pre_mean * (math.exp(res["estimate"]) - 1),
            }
        )
    return pd.DataFrame(rows)


def fdr_table(did_path: Path, github_path: Path | None = None) -> pd.DataFrame:
    did = read_csv(did_path)
    rows = []
    for _, row in did.iterrows():
        rows.append(
            {
                "family": "stackoverflow_baseline",
                "outcome": row["outcome"],
                "p_value": row["p_value"],
                "estimate": row["estimate"],
            }
        )
    if github_path and github_path.exists():
        gh = read_csv(github_path)
        gh = gh[gh["treatment"].eq("so_dependence_log")]
        for _, row in gh.iterrows():
            rows.append(
                {
                    "family": "github_extension",
                    "outcome": row["outcome"],
                    "p_value": row["p_value"],
                    "estimate": row["coefficient"],
                }
            )
    out = pd.DataFrame(rows)
    out["q_value_bh_fdr"] = multipletests(out["p_value"].astype(float), method="fdr_bh")[1]
    out["significant_5pct_after_fdr"] = out["q_value_bh_fdr"] < 0.05
    return out


def sample_sensitivity(df: pd.DataFrame) -> pd.DataFrame:
    totals = df[df["week_start"] < pd.Timestamp(CHATGPT_RELEASE_DATE)].groupby("tag")["questions"].sum().sort_values(ascending=False)
    samples: dict[str, pd.DataFrame] = {
        "top_50": df[df["tag"].isin(totals.head(50).index)].copy(),
        "top_100": df[df["tag"].isin(totals.head(100).index)].copy(),
        "exclude_top_10": df[~df["tag"].isin(totals.head(10).index)].copy(),
        "exclude_ai_ml_tags": df[~df["tag"].isin(AI_ML_TAGS)].copy(),
        "balanced_active": df.groupby("tag").filter(lambda g: (g["questions"] > 0).mean() > 0.95).copy(),
    }
    rows = []
    for sample_name, sample_df in samples.items():
        for outcome in ["log_questions", "log_answers"]:
            res = did_panel(sample_df, outcome)
            rows.append({"sample": sample_name, **res})
    return pd.DataFrame(rows)


def stress_tests(df: pd.DataFrame, matched: pd.DataFrame, ppml: pd.DataFrame, inference: pd.DataFrame, placebo: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for outcome in ["log_questions", "log_answers"]:
        base = did_panel(df, outcome)
        linear = smf.ols(
            f"{outcome} ~ ai_x_post + C(tag) + C(week_start) + C(tag):week_index",
            data=df,
        ).fit(cov_type="cluster", cov_kwds={"groups": df["tag"]})
        rows.append({"test": "Baseline TWFE", "outcome": outcome, "estimate": base["estimate"], "p_value": base["p_value"], "interpretation": "core estimate"})
        rows.append({"test": "Tag-specific linear trends", "outcome": outcome, "estimate": linear.params["ai_x_post"], "p_value": linear.pvalues["ai_x_post"], "interpretation": "controls simple differential tag trends"})
        m = matched[matched["outcome"].eq(outcome)].iloc[0]
        rows.append({"test": "Matched pre-trends", "outcome": outcome, "estimate": m["matched_sample_estimate"], "p_value": np.nan, "interpretation": "Mahalanobis high-low tag matched sample"})
        tw = inference[inference["outcome"].eq(outcome)].iloc[0]
        rows.append({"test": "Two-way clustering", "outcome": outcome, "estimate": tw["estimate"], "p_value": tw["two_way_cluster_p"], "interpretation": "clustered by tag and week"})
        p = placebo[(placebo["outcome"].eq(outcome)) & (placebo["placebo_type"].eq("real_chatgpt"))].iloc[0]
        rows.append({"test": "Real shock vs placebos", "outcome": outcome, "estimate": p["estimate"], "p_value": p["p_value"], "interpretation": "compare with placebo distribution file"})
    for outcome in ["questions", "answers"]:
        p = ppml[ppml["outcome"].eq(outcome)].iloc[0]
        rows.append({"test": "PPML FE", "outcome": outcome, "estimate": p["estimate"], "p_value": p["p_value"], "interpretation": f"IRR={p['irr']:.3f}"})
    return pd.DataFrame(rows)


def run(args: argparse.Namespace) -> dict[str, Path]:
    df = prepare_panel(args.input)
    ensure_directories()
    outputs = {}

    slope = slope_pretrend_tests(df)
    event_rows = []
    joint_rows = [slope]
    for outcome in ["log_questions", "log_answers"]:
        ev, jt = binned_event_study(df, outcome, bin_weeks=13)
        event_rows.append(ev)
        joint_rows.append(jt)
    event = pd.concat(event_rows, ignore_index=True)
    pretests = pd.concat(joint_rows, ignore_index=True)

    placebo = placebo_table(df)
    rolling = rolling_placebos(df)
    features = tag_pre_features(df)
    matches = mahalanobis_matched_tags(features)
    matched = matched_did(df, matches)
    ppml = ppml_fe(df)
    inference = inference_table(df)
    effects = effect_sizes(df)
    fdr = fdr_table(args.did_table, args.github_table)
    sensitivity = sample_sensitivity(df)
    stress = stress_tests(df, matched, ppml, inference, placebo)

    tables = {
        "pretrend_tests": pretests,
        "binned_event_study": event,
        "placebo_dates": placebo,
        "rolling_placebos": rolling,
        "matching_features": features,
        "matched_pairs": matches,
        "matched_did": matched,
        "ppml_fe": ppml,
        "inference": inference,
        "effect_sizes": effects,
        "fdr": fdr,
        "sample_sensitivity": sensitivity,
        "stress_tests": stress,
    }
    for name, table in tables.items():
        path = args.output_dir / f"referee_{name}.csv"
        write_csv(table, path)
        outputs[name] = path
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run referee-grade methodological diagnostics for Stack Overflow first-pass results.")
    parser.add_argument("--input", type=Path, default=PROCESSED_DIR / "stackoverflow_tag_week_panel_real.csv")
    parser.add_argument("--did-table", type=Path, default=TABLES_DIR / "stackoverflow_did_real.csv")
    parser.add_argument("--github-table", type=Path, default=TABLES_DIR / "github_entry_top1000_language_entry_models.csv")
    parser.add_argument("--output-dir", type=Path, default=TABLES_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger = get_logger(__name__)
    outputs = run(args)
    for key, path in outputs.items():
        logger.info("Wrote %s to %s", key, path)


if __name__ == "__main__":
    main()
