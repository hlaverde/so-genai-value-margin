# Methodological Upgrade Status

This note tracks the transition from a first-pass empirical design to a referee-facing design for *Technology in Society*.

## Completed With Current Data

Script:

- `src/models/referee_grade_diagnostics.py`

Generated outputs:

- `outputs/tables/referee_pretrend_tests.csv`
- `outputs/tables/referee_binned_event_study.csv`
- `outputs/tables/referee_placebo_dates.csv`
- `outputs/tables/referee_rolling_placebos.csv`
- `outputs/tables/referee_matching_features.csv`
- `outputs/tables/referee_matched_pairs.csv`
- `outputs/tables/referee_matched_did.csv`
- `outputs/tables/referee_ppml_fe.csv`
- `outputs/tables/referee_inference.csv`
- `outputs/tables/referee_effect_sizes.csv`
- `outputs/tables/referee_fdr.csv`
- `outputs/tables/referee_sample_sensitivity.csv`
- `outputs/tables/referee_stress_tests.csv`
- `outputs/figures/referee_rolling_placebo_distribution.png`

## Main Diagnostic Findings

### Pre-trends

Formal pre-trend tests reject flat differential pre-trends:

- `log_questions`: slope test p = 0.0019; binned pre-period joint F-test p < 0.001.
- `log_answers`: slope test p < 0.001; binned pre-period joint F-test p < 0.001.
- `log_unique_users`: slope test p = 0.0023.

Interpretation: the paper should not claim a clean parallel-trends causal design without correction or sensitivity analysis. The stronger current claim is quasi-experimental/descriptive, with trend-robust specifications as partial mitigation.

### Temporal placebos

Fixed-date placebos in 2019, 2020, 2021, and June 2022 are positive for `log_questions` and `log_answers`, while the real November 2022 coefficient is negative. This is encouraging because the true shock is not simply replicating the sign of prior placebo shocks.

### Matched pre-trends

Mahalanobis matching of high-answerability tags to low-answerability tags on pre-period levels, slopes, volatility, maturity, code share, closure share, and answer rate yields:

- `log_questions`: full sample = -0.301; matched sample = -0.267.
- `log_answers`: full sample = -0.254; matched sample = -0.223.
- `short_code_share`: full sample = -0.034; matched sample = -0.038.

Interpretation: the main sign survives matched pre-period comparisons, with somewhat attenuated activity effects.

### PPML fixed effects

PPML with tag and week fixed effects yields smaller and statistically imprecise count effects:

- Questions: IRR = 0.927, p = 0.265.
- Answers: IRR = 0.941, p = 0.359.
- Accepted answers: IRR = 0.922, p = 0.223.
- Unique users: IRR = 0.939, p = 0.360.

Interpretation: PPML is currently a warning sign. The paper should report it honestly as a co-primary count specification or explain why log models are more appropriate for the current estimand.

### Inference

Two-way clustering by tag and week leaves the main log effects statistically significant:

- `log_questions`: p < 0.001.
- `log_answers`: p < 0.001.
- `log_unique_users`: p < 0.001.

Wild cluster and block bootstrap columns are scaffolded but not yet computed. They remain a priority.

### Effect sizes

For a one-standard-deviation increase in AI answerability:

- `log_questions`: -0.301, approximately -26.0%.
- `log_answers`: -0.254, approximately -22.4%.
- `log_unique_users`: -0.288, approximately -25.1%.

### Multiple testing

Benjamini-Hochberg FDR correction preserves the Stack Overflow core outcomes:

- Questions, answers, answer rate, code share, and short-code share remain significant at 5% FDR.
- GitHub extension outcomes do not survive FDR.

## Objective AI-Answerability Validation

Manual coding was replaced with a non-manual revealed-answerability validation.

Script:

- `src/features/validate_ai_answerability_revealed.py`

Inputs:

- `data/raw/stackoverflow/stackoverflow_question_validation_pool.csv`
- `data/processed/ai_answerability_real.csv`

Outputs:

- `outputs/tables/ai_answerability_revealed_validation.csv`
- `data/processed/ai_answerability_revealed_validation_tag.csv`
- `data/processed/ai_answerability_revealed_validation_question.csv`

The validation uses only pre-ChatGPT observed question-resolution signals:

- whether the question received an answer;
- whether it received an accepted answer;
- whether it received a first answer within 6 or 24 hours;
- whether it was answered and not closed;
- minutes to first answer.

Main results:

- Tag-level Pearson correlation between current AI-answerability index and revealed answerability mean: 0.563.
- Tag-level Spearman correlation: 0.630.
- Tag-level correlation with high revealed-answerability share: 0.649.
- Correlation with fast-answer-within-24-hours share: 0.568.
- Correlation with accepted-fast-within-24-hours share: 0.498.
- Question-level Spearman correlation: 0.138.
- Question-level AUC for high revealed answerability: 0.564.

Interpretation: the current treatment has meaningful objective validation at the tag level, which is the level of treatment in the main DiD. The weaker question-level validation is expected because the treatment is intentionally aggregated at the tag level and question-level answerability is noisy.

This approach is faster and less subjective than human coding, but it validates "community-answerability" rather than direct LLM answerability. The paper should describe it as revealed pre-ChatGPT answerability validation.

## Fractional Tag Counting

The project now includes fractional-count Stack Overflow panels to address the fact that each question can have multiple tags.

Inputs:

- `data/raw/stackoverflow/stackoverflow_fractional_tag_week_2018_2019.csv`
- `data/raw/stackoverflow/stackoverflow_fractional_tag_week_2020_2021.csv`
- `data/raw/stackoverflow/stackoverflow_fractional_tag_week_2022_2023.csv`
- `data/raw/stackoverflow/stackoverflow_fractional_tag_week_2024_2026.csv`

Scripts:

- `src/data/prepare_stackoverflow_fractional.py`
- `src/models/stackoverflow_fractional_results.py`

Outputs:

- `data/processed/stackoverflow_fractional_tag_week_panel_real.csv`
- `outputs/tables/stackoverflow_fractional_did_real.csv`

Results:

- `log_questions`: -0.267, p < 0.001.
- `log_answers`: -0.235, p < 0.001.
- `log_unique_users`: -0.287, p < 0.001.
- `log_accepted_answers`: -0.286, p < 0.001.

Interpretation: the main Stack Overflow activity decline survives fractional tag counting. The magnitude for questions and answers is somewhat smaller than the full-count baseline, but the sign and statistical strength remain.

## New SQL Prepared For Required Data Upgrades

External validation and mechanism tests require additional SEDE exports:

- `sql/stackoverflow_question_validation_pool.sql`
- `sql/stackoverflow_fractional_tag_week.sql`
- `sql/stackoverflow_user_post_entry.sql`
- `sql/stackoverflow_question_type_week.sql`

Validation scripts:

- `src/features/validate_ai_answerability.py` for optional human/LLM coding.
- `src/features/validate_ai_answerability_revealed.py` for objective revealed-answerability validation.

## Priority Next Data Tasks

1. Run `stackoverflow_question_type_week.sql` to estimate the mechanism triple difference by substitutable question type.
2. Run `stackoverflow_user_post_entry.sql` in yearly windows to rebuild new-user entry and retention analysis at user-post level.
3. Optionally expand the validation pool into 2020-2022 with narrower SEDE windows if referees ask for a later pre-period validation sample.

## Current Publication Implication

The project has moved beyond a basic first pass, but the referee-facing version still needs external treatment validation and additional SEDE extracts. The core Stack Overflow result remains promising, but the formal pre-trend failures and PPML attenuation mean the manuscript must either add stronger corrections or frame the causal claim more cautiously.
