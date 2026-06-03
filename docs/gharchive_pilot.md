# GH Archive Pilot

Date: 2026-05-15.

## Goal

Assess whether GH Archive can support the GitHub-entry extension without paid APIs or BigQuery.

Requested windows:

- Placebo: 2021-11-28 to 2021-12-04.
- ChatGPT shock: 2022-11-28 to 2022-12-04.
- Later post period: 2023-11-28 to 2023-12-04.

## Feasibility Finding

A full 2022 shock week was downloaded first:

- Files: 168 hourly `.json.gz` files.
- Compressed size: 14.22 GB.

Parsing a full week is too slow for routine iteration in the current environment. A 28-file pilot also failed to complete cleanly. The practical pilot design is therefore a systematic hourly sample:

- Hour: 12:00 UTC.
- Days: each day in the target 7-day window.
- Files per window: 7.

This keeps the windows comparable while lowering disk and processing cost.

## Downloaded and Processed Windows

| window | files | compressed GB | filtered events | unique actors in window | unique repos in window |
|---|---:|---:|---:|---:|---:|
| placebo_week_2021_hour12 | 7 | 0.47 | 971,117 | 241,072 | 285,778 |
| chatgpt_week_2022_hour12 | 7 | 0.67 | 1,372,846 | 276,706 | 404,602 |
| post_week_2023_hour12 | 7 | 0.62 | 2,030,262 | 264,361 | 334,906 |

## Event Counts

| event type | 2021 placebo | 2022 shock | 2023 post |
|---|---:|---:|---:|
| CreateEvent | 147,913 | 226,813 | 133,400 |
| ForkEvent | 17,798 | 17,170 | 11,928 |
| IssueCommentEvent | 52,597 | 60,193 | 45,738 |
| IssuesEvent | 23,172 | 22,157 | 18,457 |
| PullRequestEvent | 78,451 | 148,320 | 72,994 |
| PushEvent | 601,764 | 847,545 | 1,697,297 |
| WatchEvent | 49,422 | 50,648 | 50,448 |

## First-Seen Actors Within Window

Important limitation: `first_seen_actors_in_window` means first observed within the sampled window, not first ever on GitHub. A true new-contributor measure requires longer lookback windows or repository-level first-contribution histories.

| first event type | 2021 placebo | 2022 shock | 2023 post |
|---|---:|---:|---:|
| CreateEvent | 51,118 | 59,368 | 54,322 |
| ForkEvent | 11,503 | 11,436 | 8,070 |
| IssueCommentEvent | 13,940 | 14,311 | 11,918 |
| IssuesEvent | 7,165 | 6,835 | 6,863 |
| PullRequestEvent | 6,757 | 9,434 | 10,850 |
| PushEvent | 120,212 | 143,664 | 141,036 |
| WatchEvent | 30,377 | 31,658 | 31,302 |

## Generated Files

Raw downloaded folders:

- `data/raw/gharchive/placebo_week_2021_hour12/`
- `data/raw/gharchive/chatgpt_week_2022/` full 168-hour week, retained for now.
- `data/raw/gharchive/post_week_2023_hour12/`

Processed comparative files:

- `data/processed/gharchive/comparative_hour12_summary.csv`
- `data/processed/gharchive/comparative_hour12_event_week.csv`
- `data/processed/gharchive/comparative_hour12_actor_entry_week.csv`

Window-specific processed files are also stored in `data/processed/gharchive/`.

## Next Methodological Step

The pilot is useful for feasibility and descriptive volume checks, but it is not yet enough for the paper's GitHub-entry causal extension. To estimate GitHub entry credibly, the next design should:

1. Define a manageable ecosystem mapping, likely language-level rather than repository-level.
2. Use sampled but repeated windows across many weeks, not only one week per year.
3. Construct a longer lookback for `first_seen_actor` so entry means new within a defined historical sample, not just first seen inside a week.
4. Avoid storing full repo-event panels unless a narrower repo sample is selected.
5. Consider deleting or archiving the 14.22 GB full 2022 raw week if disk pressure becomes relevant.

