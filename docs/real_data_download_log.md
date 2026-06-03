# Real Data Download Log

Last updated: 2026-05-14.

This log records real-data acquisition attempts and outcomes. It is intentionally separate from simulated-data tests.

## Downloaded Successfully

### O*NET 30.2 Database

- Source URL: https://www.onetcenter.org/dl_files/database/db_30_2_text.zip
- Raw file: `data/external/onet/db_30_2_text.zip`
- Size: 13,444,123 bytes
- SHA-256: `B5479271931796B838F7173DC0F673A9EC961B7833AC87168FD11E92E7453741`
- Extracted directory: `data/external/onet/db_30_2_text/db_30_2_text/`
- Processed outputs:
  - `data/processed/onet/onet_occupations.csv`
  - `data/processed/onet/onet_skills.csv`
  - `data/processed/onet/onet_knowledge.csv`
  - `data/processed/onet/onet_tasks.csv`
  - `data/processed/onet/onet_job_zones.csv`
  - `data/processed/onet/onet_tech_skills.csv`
- Processing script: `python -m src.data.clean_onet`

Processed table summary:

| table | rows |
|---|---:|
| occupations | 1,016 |
| skills | 62,580 |
| knowledge | 59,004 |
| tasks | 18,796 |
| job zones | 923 |
| technology skills | 32,773 |

### GH Archive Sample

- Source URL pattern: `https://data.gharchive.org/YYYY-MM-DD-H.json.gz`
- Downloaded hour: 2022-11-30 00:00 UTC
- Raw file: `data/raw/gharchive/2022-11-30-00.json.gz`
- Size: 73,743,477 bytes
- SHA-256: `9243DB4A892799532B9670FB89AD3327E100CC590225012D56DDB0E07EDA514A`
- Cleaned sample: `data/interim/gharchive_events_sample.csv`
- Cleaned rows: 141,529 filtered public events
- Processing scripts:
  - `python -m src.data.download_gharchive --start 2022-11-30-00 --end 2022-11-30-00 --output-dir data/raw/gharchive`
  - `python -m src.data.clean_gharchive --input-dir data/raw/gharchive --output data/interim/gharchive_events_sample.csv`

Implementation note: GH Archive URLs use non-padded hour values, e.g. `2022-11-30-0.json.gz`. The local filename is saved with a padded hour for stable sorting.

### GH Archive Comparative Pilot

- Protocol: `docs/gharchive_pilot.md`
- Full shock-week download: `data/raw/gharchive/chatgpt_week_2022/`, 168 hourly files, 14.22 GB compressed.
- Comparable processed pilot windows use hour 12 UTC for each day:
  - `placebo_week_2021_hour12`
  - `chatgpt_week_2022_hour12`
  - `post_week_2023_hour12`
- Processed outputs:
  - `data/processed/gharchive/comparative_hour12_summary.csv`
  - `data/processed/gharchive/comparative_hour12_event_week.csv`
  - `data/processed/gharchive/comparative_hour12_actor_entry_week.csv`

### GH Archive Definitive Sample Start

- Protocol: `docs/gharchive_definitive_sample.md`
- Calendar: Monday and Thursday at 12:00 UTC, 2021-2024.
- Calendar file: `data/raw/gharchive/gharchive_sample_calendar_2021_2024_mon_thu_12utc.csv`
- 2021 downloaded files: 101 of 104 planned hours.
- 2021 missing hours: 3, all HTTP 404 from GH Archive.
- 2021 processed events: 13,385,662 filtered public events.
- 2021 processed output:
  - `data/processed/gharchive/gharchive_mon_thu_12utc_2021_sample_summary.csv`
  - `data/processed/gharchive/gharchive_mon_thu_12utc_2021_sample_week_event_panel.csv`
- 2022 downloaded files: 104 of 104 planned hours.
- 2022 processed events: 17,542,550 filtered public events.
- 2022 processed output:
  - `data/processed/gharchive/gharchive_mon_thu_12utc_2022_sample_summary.csv`
  - `data/processed/gharchive/gharchive_mon_thu_12utc_2022_sample_week_event_panel.csv`
- 2023 downloaded files: 104 of 104 planned hours.
- 2023 processed events: 21,495,762 filtered public events.
- 2023 processed output:
  - `data/processed/gharchive/gharchive_mon_thu_12utc_2023_sample_summary.csv`
  - `data/processed/gharchive/gharchive_mon_thu_12utc_2023_sample_week_event_panel.csv`
- 2024 downloaded files: 105 of 105 planned hours.
- 2024 processed events: 26,988,747 filtered public events.
- 2024 processed output:
  - `data/processed/gharchive/gharchive_mon_thu_12utc_2024_sample_summary.csv`
  - `data/processed/gharchive/gharchive_mon_thu_12utc_2024_sample_week_event_panel.csv`
- Combined 2021-2024 outputs:
  - `data/processed/gharchive/gharchive_mon_thu_12utc_2021_2024_summary.csv`
  - `data/processed/gharchive/gharchive_mon_thu_12utc_2021_2024_week_event_panel.csv`

## Attempted but Not Automated

### BLS OEWS

- Source attempted: https://download.bls.gov/pub/time.series/oe/
- Result: BLS returned an Access Denied anti-bot message for automated `Invoke-WebRequest` retrieval.
- Decision: do not bypass the restriction. Treat BLS OEWS as a manual download or use a documented BLS-approved access path later.
- Status: pending.

### Stack Exchange Data Explorer / Stack Overflow

- Source: https://data.stackexchange.com/help
- Status: pending manual export.
- Attempted automation date: 2026-05-15.
- Result: SEDE loaded in a browser, but anonymous query execution required CAPTCHA. Direct `Invoke-WebRequest` access to the query page was blocked by Cloudflare. No CAPTCHA bypass was attempted.
- Reason: the core Stack Overflow extracts require running the project SQL files in Stack Exchange Data Explorer and exporting CSV query results. This is still the preferred no-cost route because it avoids paid APIs, avoids BigQuery costs, and avoids downloading the very large full Stack Overflow data dump.
- Expected files:
  - `data/raw/stackoverflow/stackoverflow_tag_week.csv`
  - `data/raw/stackoverflow/stackoverflow_user_tag_week.csv`
  - `data/raw/stackoverflow/stackoverflow_post_complexity.csv`
- Protocol: `docs/stackoverflow_sede_download.md`

### IPUMS CPS

- Source: https://cps.ipums.org/cps/
- Status: pending.
- Reason: IPUMS CPS requires user registration and terms acceptance. It remains a secondary validation module, not part of the first automated download pass.

## Manifest

The hash manifest for downloaded raw/interim files is stored at:

- `data/external/download_manifest.csv`
