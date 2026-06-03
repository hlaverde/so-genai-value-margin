# Stack Exchange Data Explorer SQL

Run these queries manually in Stack Exchange Data Explorer against the Stack Overflow database and export CSV results.

Expected filenames for the default cleaning script:

- `stackoverflow_tag_week.csv`
- `stackoverflow_user_tag_week.csv`
- `stackoverflow_post_complexity.csv`

The SQL is intentionally simple for the first iteration. If SEDE timeouts occur, split by year and append downloaded CSV files with a documented script rather than manual spreadsheet editing.
