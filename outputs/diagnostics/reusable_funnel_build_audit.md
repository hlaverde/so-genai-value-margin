# Reusable Funnel — Build Audit

_Generated: 2026-05-26T11:53:18_


## Audit metrics

- **files_loaded**: 475
- **rows_pre_alias**: 8404411
- **rows_pre_dedup**: 8404411
- **rows_post_dedup**: 8404411
- **rows_dropped_dedup**: 0
- **memory_mb**: 1313.077837
- **load_elapsed_s**: 38.3
- **panel_rows_after_groupby**: 164351
- **panel_unique_tags**: 100
- **panel_unique_question_types**: 7
- **panel_unique_weeks**: 261
- **panel_week_min**: 2020-01-06
- **panel_week_max**: 2024-12-30
- **total_questions_count**: 8383357
- **total_answered**: 6762389
- **total_accepted**: 3647519
- **total_accepted_nonclosed**: 3464179
- **total_accepted_nonneg**: 3301601
- **total_reusable**: 3187633
- **monotonicity_violations**:
  - ✅ `reusable_artifacts <= accepted_nonnegative_questions` violations: 0
  - ✅ `accepted_nonnegative_questions <= accepted_answer_questions` violations: 0
  - ✅ `accepted_nonclosed_questions <= accepted_answer_questions` violations: 0
  - ✅ `accepted_answer_questions <= answered_questions` violations: 0
  - ✅ `answered_questions <= questions_count` violations: 0
- **after_merge_rows**: 164351
- **rows_missing_answerability**: 0
- **panel_cells_pre**: 99185
- **panel_cells_post**: 65166
- **output_path**: D:\DocumentosHL\Documentos\Documents\2021\Henry Laverde\2026\Investigación\Paper de IA\Propuesta No. 1\ai-knowledge-commons-shock\data\processed\reusable_artifact_funnel_panel.csv
- **output_size_mb**: 20.31

## First 5 rows of output panel

| tag   | week_start          | question_type         |   substitutable_type |   questions_count |   answered_questions |   accepted_answer_questions |   accepted_nonclosed_questions |   accepted_nonnegative_questions |   reusable_artifacts |   ai_answerability_zscore |   ai_answerability_pca |   ai_answerability_quantile |   ai_answerability_structural |   post_chatgpt | post_chatgpt_bool   |
|:------|:--------------------|:----------------------|---------------------:|------------------:|---------------------:|----------------------------:|-------------------------------:|---------------------------------:|---------------------:|--------------------------:|-----------------------:|----------------------------:|------------------------------:|---------------:|:--------------------|
| .net  | 2020-01-06 00:00:00 | advanced_architecture |                    0 |                 3 |                    3 |                           1 |                              1 |                                1 |                    1 |                 -0.570197 |               -1.05936 |                           0 |                     -0.484784 |              0 | False               |
| .net  | 2020-01-06 00:00:00 | debugging_simple      |                    1 |                22 |                   17 |                           2 |                              2 |                                2 |                    2 |                 -0.570197 |               -1.05936 |                           0 |                     -0.484784 |              0 | False               |
| .net  | 2020-01-06 00:00:00 | how_to                |                    1 |                56 |                   47 |                          28 |                             26 |                               24 |                   23 |                 -0.570197 |               -1.05936 |                           0 |                     -0.484784 |              0 | False               |
| .net  | 2020-01-06 00:00:00 | long_code             |                    1 |                79 |                   65 |                          38 |                             36 |                               36 |                   35 |                 -0.570197 |               -1.05936 |                           0 |                     -0.484784 |              0 | False               |
| .net  | 2020-01-06 00:00:00 | other_conceptual      |                    1 |                38 |                   30 |                          13 |                             11 |                               11 |                   10 |                 -0.570197 |               -1.05936 |                           0 |                     -0.484784 |              0 | False               |