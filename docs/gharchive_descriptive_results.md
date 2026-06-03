# GH Archive Descriptive Results

Date: 2026-05-15.

## Scope

This document summarizes aggregate GitHub activity from the systematic GH Archive sample:

- Monday and Thursday.
- 12:00 UTC.
- 2021-2024.
- Public GH Archive events only.

This is the **Camino A** descriptive extension. It does not yet test H4 because events are not mapped to language/ecosystem dependence on Stack Overflow.

## Generated Outputs

Tables:

- `outputs/tables/gharchive_prepost_descriptives.csv`
- `outputs/tables/gharchive_weekly_totals.csv`
- `outputs/tables/gharchive_event_weekly.csv`

Figures:

- `outputs/figures/gharchive_total_weekly_series.png`
- `outputs/figures/gharchive_events_by_type_weekly.png`
- `outputs/figures/gharchive_first_seen_actors_by_type_weekly.png`

## Aggregate Pre/Post Patterns

The pre period is before 2022-11-30. The post period is on or after 2022-11-30.

Events per sampled week:

| event type | pre | post |
|---|---:|---:|
| CreateEvent | 48,997 | 56,304 |
| ForkEvent | 5,393 | 4,778 |
| IssueCommentEvent | 19,334 | 20,228 |
| IssuesEvent | 7,350 | 7,849 |
| PullRequestEvent | 29,908 | 31,919 |
| PushEvent | 170,594 | 319,622 |
| WatchEvent | 14,819 | 18,655 |

First-seen actors per sampled week:

| event type | pre | post |
|---|---:|---:|
| CreateEvent | 11,069 | 13,318 |
| ForkEvent | 2,814 | 2,373 |
| IssueCommentEvent | 2,285 | 2,204 |
| IssuesEvent | 1,350 | 1,420 |
| PullRequestEvent | 1,018 | 1,343 |
| PushEvent | 20,331 | 25,536 |
| WatchEvent | 5,938 | 7,308 |

## Initial Reading

At the aggregate GitHub level, there is no simple visible collapse in public GitHub activity after ChatGPT in this sampled design. Aggregate `PushEvent`, `CreateEvent`, `WatchEvent`, and first-seen actors grow post-ChatGPT.

This does not contradict the Stack Overflow result because the hypothesized mechanism is not a general collapse of GitHub activity. H4 is narrower: ecosystems historically more dependent on Stack Overflow may have weaker entry relative to less dependent ecosystems. Testing that requires an ecosystem/language mapping.

## Limitations

- The sample observes two hours per week, not the full GH Archive universe.
- `first_seen_actors_in_sample` means first seen in the sampled stream, not necessarily first ever on GitHub.
- Current first-seen processing is annual; the next version should maintain state across 2021-2024.
- No language or ecosystem mapping is included yet.
- Repository-level panels are intentionally not materialized because they are too large without narrowing the repo sample.

## Next Step Toward H4

Move from aggregate GitHub descriptives to ecosystem-level panels:

1. Create a language/ecosystem taxonomy aligned with Stack Overflow tags.
2. Build `SO_Dependence_l` from pre-ChatGPT Stack Overflow tag volume.
3. Identify a reproducible way to map GitHub repositories/events to ecosystems.
4. Estimate:

```text
GithubEntry_lw = alpha_l + lambda_w + beta * SO_Dependence_l x PostChatGPT_w + epsilon_lw
```

