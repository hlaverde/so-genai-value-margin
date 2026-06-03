"""The decision artefact: a value-calibrated early-warning report.

A platform manager runs this on the (tag, week, question-type) panel and
gets a per-tag table with three layers:
  (1) DETECTION  -- the activity-deficit signal (the signal validated
      out of sample as the sufficient detector of high-value erosion,
      AUC 0.82; see 21_vtd_validation.py / 25_vtd_voi.py);
  (2) CALIBRATION -- expected high-value posts at risk = activity deficit
      x the tag's high-value share, converting an activity alert into the
      decision-relevant high-value quantity using the value-margin
      estimates;
  (3) COMPOSITION FLAG -- the VtD disproportionality (secondary,
      persistent rho=0.83) with a bootstrap CI, classifying whether a
      tag's decline is value-disproportionate (informs intervention TYPE,
      not whether to act).
A graphical UI and a user study are out of scope (no subjects available).

Run: python src/analysis/23_vtd_monitor_report.py
Output: outputs/models/vtd_monitor_report.csv + console alert list.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

THIS = Path(__file__).resolve(); ROOT = THIS.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.paths import PROCESSED_DIR, OUTPUTS_DIR  # noqa: E402

CHATGPT = pd.Timestamp("2022-11-30")
VW = PROCESSED_DIR / "value_weighted_funnel_panel.csv"
AI = "ai_answerability_structural"
BETA_ACT, BETA_HV = -0.108, -0.131
THETA = 0.196            # loss-derived flagging threshold (see 21_*)
RNG = np.random.default_rng(20260601)


def vtd_per_tag(df):
    post = df[df["week_start"] >= CHATGPT].copy()
    g = post["ai"] * post["sub"]
    post["d_act"] = post["questions_count"] * (np.exp(-BETA_ACT * g) - 1)
    post["d_hv"] = post["high_value_artifacts"] * (np.exp(-BETA_HV * g) - 1)
    by = post.groupby("tag").agg(d_act=("d_act", "sum"),
                                 d_hv=("d_hv", "sum")).reset_index()
    by = by[by["d_act"] > 0]
    by["VtD"] = by["d_hv"] / by["d_act"]
    # (1) detection: activity-deficit signal; (2) calibration: expected
    # high-value posts at risk = activity deficit * tag high-value share.
    by["activity_at_risk"] = by["d_act"]
    by["hv_at_risk"] = by["d_hv"]   # = activity deficit * hv share, by construction
    return by, post


def main():
    df = pd.read_csv(VW); df["week_start"] = pd.to_datetime(df["week_start"])
    df["ai"] = df[AI].astype(float); df["sub"] = df["substitutable_type"].astype(int)
    by, post = vtd_per_tag(df)

    # bootstrap per-tag VtD CIs by resampling weeks within tag
    tags = by["tag"].tolist()
    boot = {t: [] for t in tags}
    post_g = {t: d for t, d in post.groupby("tag")}
    for _ in range(1000):
        for t in tags:
            d = post_g[t]
            s = d.sample(len(d), replace=True, random_state=RNG.integers(1e9))
            gg = s["ai"] * s["sub"]
            da = (s["questions_count"] * (np.exp(-BETA_ACT * gg) - 1)).sum()
            dh = (s["high_value_artifacts"] * (np.exp(-BETA_HV * gg) - 1)).sum()
            boot[t].append(dh / da if da > 0 else np.nan)
    by["ci_lo"] = by["tag"].map(lambda t: np.nanpercentile(boot[t], 2.5))
    by["ci_hi"] = by["tag"].map(lambda t: np.nanpercentile(boot[t], 97.5))
    by["alert"] = (by["ci_lo"] > THETA).astype(int)   # whole CI above theta
    by = by.sort_values("hv_at_risk", ascending=False).reset_index(drop=True)
    by = by[["tag", "activity_at_risk", "hv_at_risk", "VtD",
             "ci_lo", "ci_hi", "alert"]]
    by.to_csv(OUTPUTS_DIR / "models" / "vtd_monitor_report.csv", index=False)
    n_alert = int(by["alert"].sum())
    print(f"theta = {THETA};  tags monitored = {len(by)};  "
          f"composition-flag ALERTS (CI above theta) = {n_alert}")
    print("\nTag          act@risk  HV@risk   VtD    95% CI         flag")
    for _, r in by.head(15).iterrows():
        print(f"{r['tag']:<12} {r['activity_at_risk']:8.0f} "
              f"{r['hv_at_risk']:7.0f}  {r['VtD']:.3f}  "
              f"[{r['ci_lo']:.2f},{r['ci_hi']:.2f}]  "
              f"{'FLAG' if r['alert'] else ''}")


if __name__ == "__main__":
    main()
