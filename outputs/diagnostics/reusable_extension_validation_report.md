# Reusable Funnel Extension — Validation Report

_Generated: 2026-05-26T11:54:40_

Each check below produces a hard pass/fail.

If any check fails, downstream tables/figures must be revisited before submission.


## Results

- [OK] **Monotonicity holds across all funnel chains** - 
  - [OK] `reusable_artifacts <= accepted_nonnegative_questions`: 0 violations across 164,351 cells
  - [OK] `accepted_nonnegative_questions <= accepted_answer_questions`: 0 violations across 164,351 cells
  - [OK] `accepted_nonclosed_questions <= accepted_answer_questions`: 0 violations across 164,351 cells
  - [OK] `accepted_answer_questions <= answered_questions`: 0 violations across 164,351 cells
  - [OK] `answered_questions <= questions_count`: 0 violations across 164,351 cells
- [OK] **All resolvability shares in [0,1]** - all share columns in [0,1] (numeric tolerance 1e-9)
- [OK] **100 unique tags in funnel panel** - n_tags=100
- [OK] **7 unique question_types** - n_qt=7
- [OK] **post_chatgpt flag matches threshold 2022-11-30** - threshold pre/post=99185/65166, flag pre/post=99185/65166
- [OK] **DDD baseline (questions_count) within 0.03 of -0.108** - beta=-0.1082, diff=-0.0002
- [OK] **Implied displacement (questions_count) within 10% of 67,000** - implied=70,364, deviation=5.0%
- [OK] **Trend shortfall (questions) within 5% of 1.42M** - trend_shortfall=1,418,907, dev=0.08%
- [OK] **DDD share of trend shortfall within [3%, 8%] (baseline ~4-5%)** - share=4.96%
- [OK] **Zero missing in key funnel columns** - no missing
- [OK] **Panel cell count matches master panel (164,351)** - cells=164,351

## Summary

**Overall status:** `ALL CHECKS PASSED`

**Checks run:** 11  
**Passed:** 11  
**Failed:** 0