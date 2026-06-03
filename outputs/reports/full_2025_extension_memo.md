# Full 2025 Stack Overflow Extension Data-Readiness Memo

## 1. Data collection status

The full 100-tag 2025 Stack Overflow API collection is complete after selective monthly repair of initially suspicious tags.

- Raw folder: `data/raw/stackoverflow/api_2025_full_100tags/`
- Manifest: `data/raw/stackoverflow/api_2025_full_100tags/manifest_2025_full_100tags.csv`
- Tag folders: 100
- JSON files: 1,465
- Manifest rows: 184 complete rows
- Failed windows: 0 observed
- Page-cap flags: 0
- Last manifest quota remaining: 8,510
- Quota interruption: no
- Resumable: yes

Selective repair was run for `ajax`, `docker`, `loops`, `opencv`, and `postgresql` using monthly windows. This resolved the probable truncation in `docker` and `postgresql`; the remaining late-year empty weeks for `ajax`, `loops`, and `opencv` are documented as observed zero/low activity rather than raw download failures.

## 2. Raw data status

Raw audit:

- `outputs/tables/audit_2025_raw_files.csv`

Result:

- 100/100 fixed tags have raw folders.
- 100/100 fixed tags have JSON files.
- Raw-file status is `ok_raw_present` for all 100 tags.
- No failed-window file is present.
- No page-cap/truncation flag appears in the manifest.

## 3. Cleaned 2025 data status

Cleaned file:

- `data/processed/stackoverflow_2025_clean_question_tag.csv`

Summary:

- Question-tag rows: 132,511
- Unique questions: 87,027
- Tags: 100
- Duplicate `question_id x tag_consulted` rows: 0
- Date range: 2025-01-01 00:21:22 to 2025-12-31 23:14:43
- Week range: 2024-12-30 to 2025-12-29
- Weeks observed overall: 53

The clean file preserves the question-tag structure and includes required fields where available: `question_id`, `tag`, `tag_consulted`, `creation_date`, `week`, `score`, `answer_count`, `is_answered`, `accepted_answer_id`, `closed_date`, `owner_user_id`, `title`, `tags_original`, `body_length`, `has_code`, and `source`.

## 4. Coverage audit

Coverage audit:

- `outputs/tables/audit_2025_full_coverage.csv`

Result:

- 100/100 fixed tags appear.
- 100/100 tags have status `ok`.
- Failed windows: 0
- Page-cap flags: 0
- Blocking suspicious cases: 0

There are 37 tags with `missing_observed_weeks` in the 2024-2025 comparison table. These are weeks with no observed questions for that tag, not missing raw windows. The monthly repair confirms late-year windows for the previously suspicious tags.

## 5. 2024-2025 comparison

Comparison table:

- `outputs/tables/tag_counts_2024_2025.csv`

It includes `questions_2024`, `questions_2025`, `pct_change_2024_2025`, `ai_answerability_structural_if_available`, and `suspicious_flag`.

No tag is currently flagged for zero 2025 observations, implausibly low repaired coverage, failed windows, page-cap issues, or early truncation.

## 6. Panel status

Panel:

- `data/processed/panel_tag_week_question_type_2020_2025.csv`

Panel audit:

- `outputs/tables/audit_panel_2020_2025.csv`

Panel summary:

- Rows: 186,188
- Tags: 100
- Question types: 7
- Weeks: 313
- Min week: 2020-01-06
- Max week: 2025-12-29
- 2025 rows: 21,673
- 2025 tags: 100
- 2025 question types: 7
- Duplicate `tag x week x question_type` cells: 0

The previous 2020-2024 panel matches exactly for weeks before 2024-12-30. The crossing week starting 2024-12-30 is intentionally consolidated because it contains late-2024 and early-2025 questions.

## 7. Readiness decision

**READY FOR MODEL ESTIMATION**

The 2025 database and 2020-2025 panel are ready for later empirical analysis. Models were not run in this task.

## 8. Next model commands, not executed

```powershell
python -m src.analysis.estimate_ddd_2020_2025_full
python -m src.analysis.event_study_quarterly_2020_2025_full
python -m src.analysis.donut_did_moderator_strike_2020_2025
python -m src.analysis.monitor_voi_regret_2025_full
```
