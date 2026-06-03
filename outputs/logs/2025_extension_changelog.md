# 2025 Extension Changelog

## Commands run

- Checked active Python fetch process before starting any new download.
- Monitored `data/raw/stackoverflow/api_2025_full_100tags/`.
- Monitored `data/raw/stackoverflow/api_2025_full_100tags/manifest_2025_full_100tags.csv`.
- Repaired suspicious tags with selective monthly API windows:
  - `ajax`
  - `docker`
  - `loops`
  - `opencv`
  - `postgresql`
- Ran `python -m src.data.build_stackoverflow_2025_clean`.
- Ran `python -m src.data.build_panel_2020_2025`.
- Generated panel audit with a consistency check against the prior 2020-2024 panel.

## Files created or updated

- `data/processed/stackoverflow_2025_clean_question_tag.csv`
- `data/processed/panel_tag_week_question_type_2020_2025.csv`
- `outputs/tables/audit_2025_raw_files.csv`
- `outputs/tables/audit_2025_full_coverage.csv`
- `outputs/tables/tag_counts_2024_2025.csv`
- `outputs/tables/audit_panel_2020_2025.csv`
- `outputs/reports/full_2025_extension_memo.md`
- `outputs/logs/2025_extension_changelog.md`

## Code modified

- `src/data/fetch_stackoverflow_2025_full_100tags.py`
  - Fixed `--initial-level monthly` so it creates true monthly windows.
  - Added selective `--force-tags` repair support.
- `src/data/build_stackoverflow_2025_clean.py`
  - Added raw-file audit.
  - Added requested coverage-audit columns.
  - Added explicit missing-observed-week and truncation flags.
  - Fixed real-JSON `source_file` handling.
- `src/data/build_panel_2020_2025.py`
  - Added `week` alias for `week_start`.
  - Consolidated duplicate crossing-week cells when appending 2025 to the existing panel.

## Errors encountered and fixes

- The first repair attempt used semestral windows because of a windowing bug. Fixed and reran monthly windows.
- Panel construction initially failed with duplicate cells for the week starting 2024-12-30. Fixed by consolidating crossing-week cells and recalculating shares.

## Final raw status

- Tag folders: 100
- JSON files: 1,465
- Manifest rows: 184 complete
- Failed windows: 0
- Page-cap flags: 0

## Final clean status

- Clean 2025 rows: 132,511
- Unique questions: 87,027
- Tags: 100
- Date range: 2025-01-01 00:21:22 to 2025-12-31 23:14:43

## Final panel status

- Panel path: `data/processed/panel_tag_week_question_type_2020_2025.csv`
- Rows: 186,188
- Tags: 100
- Question types: 7
- Weeks: 313
- Status: ready for model estimation

## Final readiness status

READY FOR MODEL ESTIMATION.
