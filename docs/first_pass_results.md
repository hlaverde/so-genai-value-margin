# First-Pass Real Stack Overflow Results

Date: 2026-05-15.

These are first-pass results from real Stack Overflow SEDE extracts. They are not yet final paper estimates.

## Data Used

- Top 100 Stack Overflow tags by pre-ChatGPT question volume.
- Weekly panel from 2018-01-01 to 2026-05-04.
- Treatment date: 2022-11-30.
- Main treatment intensity: pre-ChatGPT `AI_Answerability` at the tag level.
- User-group panel available from 2021 through 2023 for:
  - `new_user`
  - `low_reputation_user`

Processed files:

- `data/processed/stackoverflow_tag_week_panel_real.csv`
- `data/processed/stackoverflow_complexity_tag_week_real.csv`
- `data/processed/stackoverflow_user_group_tag_week_real.csv`
- `data/processed/ai_answerability_real.csv`

## Descriptive Facts

Pre-ChatGPT top-100-tag panel:

- 25,627 tag-weeks.
- 11,795,287 questions.
- Mean answer rate: 0.822.
- Mean body length: 1,861 characters.

Post-ChatGPT panel:

- 17,376 tag-weeks.
- 1,802,801 questions.
- Mean answer rate: 0.747.
- Mean body length: 2,552 characters.

The raw post-period totals are mechanically affected by fewer post-period weeks in the current panel, so causal interpretation comes from fixed-effects models, not totals.

## Baseline DID

Specification:

```text
Y_tw = tag FE + week FE + beta * AI_Answerability_t x PostChatGPT_w + epsilon_tw
```

Clustered standard errors by tag.

Main coefficients:

| outcome | beta | p-value |
|---|---:|---:|
| log(1 + questions) | -0.301 | 0.000016 |
| log(1 + answers) | -0.254 | 0.000131 |
| answer rate | 0.021 | 0.004397 |
| accepted answer share | -0.008 | 0.181 |
| average body length | -49.321 | 0.205 |
| code share | -0.023 | 0.000002 |
| how-to/error title share | -0.001 | 0.757 |
| short code share | -0.034 | < 0.000001 |

Initial interpretation: higher-AI-answerability tags experienced a larger relative decline in public questions and answers after ChatGPT. The remaining questions also appear less likely to be short code questions.

## User-Group Heterogeneity

The user-level SEDE export hit the 50,000-row limit, so the usable extract is a tag-week-user-group panel.

Specification includes tag-group fixed effects and week fixed effects. The baseline `AI_Answerability x PostChatGPT` effect remains negative for posts, questions, answers, and unique users. Additional new-user and low-reputation interactions are negative for new users but imprecise in this first specification.

Key result for `log_questions`:

- `AI_Answerability x PostChatGPT`: -0.173, p = 0.0014.
- Additional interaction for `new_user`: -0.089, p = 0.302.
- Additional interaction for `low_reputation_user`: 0.026, p = 0.767.

Initial interpretation: user-group evidence is directionally consistent with decline, but this first-pass specification does not yet provide precise evidence that new users were differentially affected beyond the general high-answerability decline.

## Robustness Checks

The baseline result is robust to:

- Excluding AI/ML-related tags.
- Dropping an 8-week transition window around ChatGPT release.

For `log(1 + questions)`:

| sample | beta |
|---|---:|
| baseline | -0.301 |
| exclude AI/ML tags | -0.313 |
| no transition 8 weeks | -0.315 |

Placebo date in the pre-period, 2021-11-30, does not produce the same negative question effect; it gives a positive coefficient for log questions. However, some complexity measures do move in placebo tests.

## Identification Warning

The event-study for `log(1 + questions)` shows non-zero pre-period coefficients in some bins. The post-period decline becomes much larger and more persistent after ChatGPT, but pre-trends are not perfectly flat.

This means the current evidence should be framed as strong descriptive/quasi-experimental first-pass evidence, not yet final causal proof. Next specifications should add:

- Tag-specific linear or flexible pre-trends.
- Matched/tag-weighted comparisons by pre-period trends.
- Placebo dates across multiple pre-period years.
- Alternative treatment indices.
- Exclusion of transition weeks and high-growth framework tags.

## Identification Strengthening Update

Additional checks were generated in `outputs/tables/stackoverflow_identification_grid_real.csv`.

Pre-trend slope correlations with `AI_Answerability`:

| outcome | correlation |
|---|---:|
| log questions | 0.256 |
| log answers | 0.327 |
| code share | -0.367 |
| short code share | -0.270 |

These correlations confirm that pre-trends are relevant and should be addressed directly.

When adding tag-specific linear trends, the main activity results remain negative:

| outcome | AI index | baseline FE beta | tag-trend beta |
|---|---|---:|---:|
| log questions | z-score | -0.301 | -0.331 |
| log questions | PCA | -0.060 | -0.087 |
| log questions | quantile | -0.393 | -0.462 |
| log questions | structural | -0.231 | -0.226 |
| log answers | z-score | -0.254 | -0.327 |
| log answers | PCA | -0.028 | -0.078 |
| log answers | quantile | -0.307 | -0.444 |
| log answers | structural | -0.167 | -0.221 |

For `log(1 + questions)` with the z-score index and tag-specific trends:

| sample | beta | p-value |
|---|---:|---:|
| baseline | -0.331 | 0.00000003 |
| exclude top 5 tags | -0.362 | 0.00000004 |
| balanced 2020-2024 | -0.214 | 0.000000000003 |
| drop transition 8 weeks | -0.362 | 0.00000004 |

Interpretation: the core activity result is not explained away by simple tag-specific linear pre-trends. However, some composition outcomes, especially code-share outcomes, are more sensitive to trend adjustments and should be framed as secondary evidence.

## Generated Outputs

Tables:

- `outputs/tables/stackoverflow_prepost_descriptives.csv`
- `outputs/tables/stackoverflow_ai_quantile_descriptives.csv`
- `outputs/tables/stackoverflow_ai_answerability_top_bottom.csv`
- `outputs/tables/stackoverflow_did_real.csv`
- `outputs/tables/stackoverflow_event_study_log_questions_real.csv`
- `outputs/tables/stackoverflow_user_group_descriptives_real.csv`
- `outputs/tables/stackoverflow_user_group_heterogeneity_real.csv`
- `outputs/tables/stackoverflow_robustness_real.csv`
- `outputs/tables/stackoverflow_pretrend_slopes_real.csv`
- `outputs/tables/stackoverflow_pretrend_ai_correlation_real.csv`
- `outputs/tables/stackoverflow_identification_grid_real.csv`

Figures:

- `outputs/figures/stackoverflow_real_time_series.png`
- `outputs/figures/stackoverflow_event_study_log_questions_real.png`
