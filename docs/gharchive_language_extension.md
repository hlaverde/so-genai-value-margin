# GH Archive language extension

This note documents the first bounded implementation of the GitHub-side mechanism:

> GitHub ecosystems that were historically more dependent on Stack Overflow may show weaker post-ChatGPT entry of new contributors.

## Current data construction

The raw GH Archive event payloads in the sampled files do not include repository file paths or repository language. Push events include commit metadata and commit URLs, but not changed files. Therefore, language cannot be inferred directly from GH Archive without another public metadata source.

The first implementation uses:

1. `data/processed/gharchive/top_repos_sample_2021_2024.csv`
   - Most active repositories in the Monday/Thursday 12:00 UTC 2021-2024 GH Archive sample.
2. GitHub public repository metadata endpoint.
   - Script: `src/data/fetch_github_repo_metadata.py`
   - Output: `data/processed/gharchive/top_repos_github_metadata.csv`
   - No paid API is used.
   - The script supports `GITHUB_TOKEN` only as an optional way to raise public API rate limits.
3. `data/processed/so_dependence_language.csv`
   - Stack Overflow historical pre-ChatGPT dependence by language/ecosystem.
4. `src/data/build_gharchive_language_panel.py`
   - Builds language-week-event panels from top repositories with public language metadata.
5. `src/models/github_entry_models.py`
   - Joins GH Archive language-week outcomes to Stack Overflow dependence and estimates exploratory fixed-effect models.

## Current outputs

- `data/processed/gharchive/top_repos_sample_2021_2024.csv`
- `data/processed/gharchive/top_repos_github_metadata.csv`
- `data/processed/gharchive/gharchive_top50_repo_language_week_event_panel.csv`
- `data/processed/gharchive/gharchive_top50_language_week_so_panel.csv`
- `outputs/tables/github_top50_language_panel_summary.csv`
- `outputs/tables/github_top50_language_entry_models.csv`

Entry-oriented extension:

- `data/processed/gharchive/entry_oriented_repos_sample_2021_2024.csv`
- `data/processed/gharchive/entry_oriented_repos_github_metadata_top200.csv`
- `data/processed/gharchive/gharchive_entry_top200_repo_language_week_event_panel.csv`
- `data/processed/gharchive/gharchive_entry_top200_language_week_so_panel.csv`
- `outputs/tables/github_entry_top200_language_panel_summary.csv`
- `outputs/tables/github_entry_top200_language_entry_models.csv`
- `data/processed/gharchive/entry_oriented_repos_github_metadata_top1000.csv`
- `data/processed/gharchive/gharchive_entry_top1000_repo_language_week_event_panel.csv`
- `data/processed/gharchive/gharchive_entry_top1000_language_week_so_panel.csv`
- `outputs/tables/github_entry_top1000_language_panel_summary.csv`
- `outputs/tables/github_entry_top1000_language_entry_models.csv`

## First-pass findings

The top-50 repository metadata run yielded 26 repositories with public primary language metadata. After joining to the Stack Overflow language-dependence index, 9 languages remain in the balanced panel.

The exploratory models do not show a precise negative GitHub-entry effect associated with higher Stack Overflow dependence. This should not be interpreted as strong evidence against the hypothesis, because the current top-repository sample is dominated by automated push activity and has very few language clusters.

The strongest current contribution of this module is diagnostic:

- GH Archive is feasible at the selected sample frequency.
- Repository language metadata can be obtained with public endpoints for bounded samples.
- A language-week panel can be reproduced locally.
- The top-active-repository design is not ideal for entry analysis because it overweights automation-heavy repositories.

## Entry-oriented sample

To reduce the influence of automated push-heavy repositories, a second sample selects repositories using only:

- PullRequestEvent
- IssuesEvent
- IssueCommentEvent
- ForkEvent
- WatchEvent

The script `src/data/build_gharchive_entry_repo_sample.py` selected 1,441 repositories from the 2021-2024 sampled GH Archive files. Public GitHub metadata was fetched for the first 200 repositories. Of these, 99 repositories had usable public primary-language metadata. After joining to the Stack Overflow dependence index, the language-week panel contains 13 Stack Overflow-linked languages and 2,717 balanced language-week rows.

The exploratory fixed-effect models in `outputs/tables/github_entry_top200_language_entry_models.csv` do not show a precise negative association between Stack Overflow dependence and post-ChatGPT GitHub entry outcomes. Coefficients for entry outcomes are generally imprecise and should be treated as diagnostic rather than as final evidence.

Using a free user-provided GitHub token, metadata coverage was expanded to the first 1,000 repositories in the entry-oriented sample. This yielded 833 repositories with public primary-language metadata. After joining to the Stack Overflow dependence index, the balanced language-week panel contains 16 Stack Overflow-linked languages and 3,344 rows.

The top-1000 exploratory models also do not show a negative differential post-ChatGPT GitHub entry effect for Stack Overflow-dependent languages. The main coefficients are small and statistically imprecise. In this version, the GitHub-side evidence is best interpreted as a null or inconclusive extension rather than support for H4.

## Main limitations

1. GH Archive does not expose repository language in event payloads.
2. Public GitHub API metadata is rate-limited without authentication.
3. Many top active repositories are deleted, blocked, automated, or have no primary language.
4. Top repositories by event count are not representative of entry-level open-source participation.
5. The entry-oriented top-1000 metadata sample improves the design but still has only 16 Stack Overflow-linked language clusters.
6. GitHub public metadata requests should be run in resumable batches. A free personal GitHub token can be used through the `GITHUB_TOKEN` environment variable; no paid API is required.

## Recommended next design

Scale the entry-oriented repository sample:

1. Identify repositories with PullRequestEvent, IssuesEvent, ForkEvent, WatchEvent, and IssueCommentEvent, not only high-volume PushEvent.
2. Fetch public language metadata in small resumable batches, preferably with a free GitHub token to avoid low unauthenticated limits.
3. Build a language-week panel focused on entry outcomes:
   - first observed actor by language;
   - first observed pull request actor;
   - first observed issue actor;
   - first observed fork actor;
   - activity in smaller repositories where entry is more meaningful.
4. Re-estimate H4 with a broader language set and document rate-limit constraints.

This keeps the project within the zero-budget rule while producing a stronger GitHub-side empirical design.
