# GH Archive Definitive Sample

Date started: 2026-05-15.

## Sampling Design

The definitive zero-budget GH Archive design uses a systematic hourly sample:

- Days: Monday and Thursday.
- Hour: 12:00 UTC.
- Planned years: 2021, 2022, 2023, 2024.
- Event types:
  - `PushEvent`
  - `PullRequestEvent`
  - `IssuesEvent`
  - `IssueCommentEvent`
  - `ForkEvent`
  - `CreateEvent`
  - `WatchEvent`

Rationale:

- Full GH Archive weeks are too heavy for routine iteration. One full 2022 week was 14.22 GB compressed.
- Monday and Thursday capture two points in the work week.
- A fixed UTC hour makes the sample reproducible and comparable across years.
- The design reduces 8,760 yearly hourly files to about 104 yearly files.

Calendar file:

- `data/raw/gharchive/gharchive_sample_calendar_2021_2024_mon_thu_12utc.csv`

Calendar size:

| year | sampled hours |
|---|---:|
| 2021 | 104 |
| 2022 | 104 |
| 2023 | 104 |
| 2024 | 105 |

## 2021 Collection Status

Downloaded folder:

- `data/raw/gharchive/sample_mon_thu_12utc_2021/`

Download status:

| status | files |
|---|---:|
| downloaded | 101 |
| 404 missing | 3 |

Missing files:

- `2021-08-26-12`
- `2021-10-25-12`
- `2021-10-28-12`

The missing files returned HTTP 404 from GH Archive. They are recorded but not imputed.

## 2021 Processed Summary

Processed outputs:

- `data/processed/gharchive/gharchive_mon_thu_12utc_2021_sample_summary.csv`
- `data/processed/gharchive/gharchive_mon_thu_12utc_2021_sample_week_event_panel.csv`

Summary:

| metric | value |
|---|---:|
| files processed | 101 |
| compressed bytes | 8,159,591,305 |
| compressed GB | 7.60 |
| filtered events | 13,385,662 |
| unique actors seen | 2,108,577 |
| unique repos seen | 3,234,606 |
| weeks observed | 51 |

Events by type:

| event type | events | first-seen actors in sample | first-seen repos in sample |
|---|---:|---:|---:|
| PushEvent | 7,435,654 | 945,431 | 1,563,430 |
| CreateEvent | 2,274,612 | 510,989 | 1,071,406 |
| PullRequestEvent | 1,381,841 | 45,493 | 121,958 |
| IssueCommentEvent | 922,901 | 115,887 | 64,970 |
| WatchEvent | 736,577 | 285,591 | 261,503 |
| IssuesEvent | 366,967 | 67,579 | 46,918 |
| ForkEvent | 267,110 | 137,607 | 104,421 |

## 2022 Collection Status

Downloaded folder:

- `data/raw/gharchive/sample_mon_thu_12utc_2022/`

Download status:

| status | files |
|---|---:|
| downloaded | 104 |
| missing/error | 0 |

Processed outputs:

- `data/processed/gharchive/gharchive_mon_thu_12utc_2022_sample_summary.csv`
- `data/processed/gharchive/gharchive_mon_thu_12utc_2022_sample_week_event_panel.csv`

Summary:

| metric | value |
|---|---:|
| files processed | 104 |
| compressed bytes | 10,720,690,711 |
| compressed GB | 9.98 |
| filtered events | 17,542,550 |
| unique actors seen | 2,470,998 |
| unique repos seen | 3,936,824 |

Events by type:

| event type | events | first-seen actors in sample |
|---|---:|---:|
| PushEvent | 10,428,505 | 1,135,740 |
| CreateEvent | 2,830,843 | 623,712 |
| PullRequestEvent | 1,763,839 | 58,339 |
| IssueCommentEvent | 1,064,568 | 115,374 |
| WatchEvent | 785,150 | 319,279 |
| IssuesEvent | 384,698 | 69,395 |
| ForkEvent | 284,947 | 149,159 |

## 2023 Collection Status

Downloaded folder:

- `data/raw/gharchive/sample_mon_thu_12utc_2023/`

Download status:

| status | files |
|---|---:|
| downloaded | 104 |
| missing/error | 0 |

Processed outputs:

- `data/processed/gharchive/gharchive_mon_thu_12utc_2023_sample_summary.csv`
- `data/processed/gharchive/gharchive_mon_thu_12utc_2023_sample_week_event_panel.csv`

Summary:

| metric | value |
|---|---:|
| files processed | 104 |
| compressed bytes | 11,164,208,868 |
| compressed GB | 10.40 |
| filtered events | 21,495,762 |
| unique actors seen | 2,701,785 |
| unique repos seen | 4,055,263 |

Events by type:

| event type | events | first-seen actors in sample |
|---|---:|---:|
| PushEvent | 14,584,976 | 1,284,573 |
| CreateEvent | 2,687,914 | 659,885 |
| PullRequestEvent | 1,592,017 | 69,076 |
| IssueCommentEvent | 1,020,987 | 118,820 |
| WatchEvent | 958,984 | 370,254 |
| IssuesEvent | 402,064 | 71,139 |
| ForkEvent | 248,820 | 128,038 |

## 2024 Collection Status

Downloaded folder:

- `data/raw/gharchive/sample_mon_thu_12utc_2024/`

Download status:

| status | files |
|---|---:|
| downloaded | 105 |
| missing/error | 0 |

Processed outputs:

- `data/processed/gharchive/gharchive_mon_thu_12utc_2024_sample_summary.csv`
- `data/processed/gharchive/gharchive_mon_thu_12utc_2024_sample_week_event_panel.csv`

Summary:

| metric | value |
|---|---:|
| files processed | 105 |
| compressed bytes | 12,763,561,932 |
| compressed GB | 11.89 |
| filtered events | 26,988,747 |
| unique actors seen | 2,986,066 |
| unique repos seen | 4,373,262 |

Events by type:

| event type | events | first-seen actors in sample |
|---|---:|---:|
| PushEvent | 19,278,531 | 1,430,372 |
| CreateEvent | 3,194,476 | 752,901 |
| PullRequestEvent | 1,702,370 | 74,322 |
| IssueCommentEvent | 1,110,440 | 116,416 |
| WatchEvent | 1,019,716 | 409,330 |
| IssuesEvent | 429,427 | 80,280 |
| ForkEvent | 253,787 | 122,445 |

## Combined 2021-2022 Outputs

- `data/processed/gharchive/gharchive_mon_thu_12utc_2021_2022_summary.csv`
- `data/processed/gharchive/gharchive_mon_thu_12utc_2021_2022_week_event_panel.csv`

## Combined 2021-2023 Outputs

- `data/processed/gharchive/gharchive_mon_thu_12utc_2021_2023_summary.csv`
- `data/processed/gharchive/gharchive_mon_thu_12utc_2021_2023_week_event_panel.csv`

## Combined 2021-2024 Outputs

- `data/processed/gharchive/gharchive_mon_thu_12utc_2021_2024_summary.csv`
- `data/processed/gharchive/gharchive_mon_thu_12utc_2021_2024_week_event_panel.csv`
- `outputs/tables/gharchive_2021_2024_summary.csv`
- `outputs/tables/gharchive_2021_2024_events_by_type.csv`
- `outputs/tables/gharchive_2021_2024_first_seen_actors_by_type.csv`
- `outputs/tables/gharchive_2021_2024_first_seen_repos_by_type.csv`

Combined summary:

| year | files | compressed GB | filtered events | unique actors seen | unique repos seen |
|---|---:|---:|---:|---:|---:|
| 2021 | 101 | 7.60 | 13,385,662 | 2,108,577 | 3,234,606 |
| 2022 | 104 | 9.98 | 17,542,550 | 2,470,998 | 3,936,824 |
| 2023 | 104 | 10.40 | 21,495,762 | 2,701,785 | 4,055,263 |
| 2024 | 105 | 11.89 | 26,988,747 | 2,986,066 | 4,373,262 |

## Interpretation of Entry Measures

`first_seen_actors_in_sample` and `first_seen_repos_in_sample` now mean first observed within the cumulative sampled GH Archive history for the year being processed. When the full 2021-2024 panel is processed sequentially, these variables will become first observed within the cumulative sampled history from 2021 onward.

For causal claims about entry, the preferred final construction should process all years in chronological order and maintain a shared first-seen state across years.

## Next Steps

1. Refactor processing to maintain first-seen state across years, not separately within each year.
2. Build GitHub outcomes at the week-event level:
   - events
   - first-seen actors
   - first-seen repos
   - first-seen pull-request actors
   - first-seen issue actors
3. Decide whether to keep raw full-week pilot files or archive/delete them after confirming the sampled design is enough.
4. Design the language/ecosystem mapping needed to connect GitHub entry outcomes to Stack Overflow dependence.
