# Stack Overflow SEDE Download Protocol

This is the required protocol for obtaining the core Stack Overflow data without paid APIs, private data, or BigQuery costs.

## Why Manual Export Is Required

Stack Exchange Data Explorer loads in a JavaScript browser session, but anonymous query execution requires a CAPTCHA. Direct scripted requests are also blocked by Cloudflare. Therefore, the reproducible workflow is:

1. Keep all SQL in version-controlled files.
2. Execute each query manually in SEDE.
3. Export CSV results without editing them.
4. Save CSVs under `data/raw/stackoverflow/`.
5. Run the repository cleaning scripts.

This preserves reproducibility because the query text, expected filenames, validation scripts, and downstream transformations are all versioned.

## Required Output Files

Save the exported CSV files with these exact names:

| SQL file | Raw CSV filename |
|---|---|
| `sql/stackoverflow_tag_week.sql` | `data/raw/stackoverflow/stackoverflow_tag_week.csv` |
| `sql/stackoverflow_user_tag_week.sql` | `data/raw/stackoverflow/stackoverflow_user_tag_week.csv` |
| `sql/stackoverflow_post_complexity.sql` | `data/raw/stackoverflow/stackoverflow_post_complexity.csv` |

If a full query times out, use the parameterized versions in `sql/sede_windows/` and save files using this pattern:

```text
data/raw/stackoverflow/windows/{query_name}_{start_year}_{end_year}.csv
```

Example:

```text
data/raw/stackoverflow/windows/stackoverflow_tag_week_2021_2022.csv
```

## Recommended Order

1. Run `stackoverflow_tag_week.sql` first. This is the main DID panel.
2. Run `stackoverflow_post_complexity.sql` second. This builds complexity and AI-answerability features.
3. Run `stackoverflow_user_tag_week.sql` third. This may be heavier; if needed, use year windows.

## Browser Steps

1. Open https://data.stackexchange.com/stackoverflow/query/new
2. Log in if needed.
3. Paste the SQL file contents.
4. Click **Run Query**.
5. Click **Download CSV**.
6. Move the file to the required path above.
7. Do not open and resave the CSV in Excel.

## Validation After Download

Run:

```powershell
python -m src.data.validate_stackoverflow_raw
```

Then run:

```powershell
python -m src.data.clean_stackoverflow --input-dir data/raw/stackoverflow --output-dir data/interim/stackoverflow
python -m src.features.build_post_complexity --input data/interim/stackoverflow/post_complexity_clean.csv --output data/processed/post_complexity_features.csv
python -m src.features.build_user_status --input data/interim/stackoverflow/user_tag_week_clean.csv --output data/processed/user_status.csv
python -m src.features.build_ai_answerability --tag-week data/interim/stackoverflow/tag_week_clean.csv --post-complexity data/processed/post_complexity_features.csv --output data/processed/ai_answerability.csv
python -m src.data.build_panels --tag-week data/interim/stackoverflow/tag_week_clean.csv --ai-answerability data/processed/ai_answerability.csv --output data/processed/stackoverflow_tag_week_panel.csv
```

## Notes

- SEDE data are periodically refreshed, so record the query date in `docs/real_data_download_log.md`.
- Keep raw exported CSV files untouched.
- If SEDE imposes row or time limits, prefer yearly windows over changing definitions.
- The first real-data audit must happen before any causal model is estimated.
