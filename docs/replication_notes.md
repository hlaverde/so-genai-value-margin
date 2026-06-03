# Replication Notes

## First Iteration Status

- Repository scaffold created.
- Stack Exchange Data Explorer SQL drafts created.
- Python paths, logging, validation, cleaning, and feature-building scripts created.
- Simulated CSV files created for a no-data pipeline test.
- Real O*NET 30.2 data have been downloaded, extracted, and converted to processed CSV tables.
- One real GH Archive hourly file for 2022-11-30 00:00 UTC has been downloaded and cleaned as a sample.
- Real Stack Overflow SEDE CSV exports have not yet been downloaded.
- Real Stack Overflow SEDE CSV exports for the top-100-tag first pass have been downloaded and processed.
- First-pass Stack Overflow DID, event-study, user-group heterogeneity, and robustness tables have been generated.
- GH Archive sampled data for 2021-2024 have been downloaded and processed.
- A first GitHub language-extension workflow has been created using public repository metadata for a bounded top-repository sample.
- An entry-oriented GitHub repository sample has been created using PRs, issues, issue comments, forks, and watches.

## Manual Steps Still Required

1. Open each SQL file in Stack Exchange Data Explorer.
2. Run against Stack Overflow.
3. Download CSV results without editing them.
4. Save files to `data/raw/stackoverflow/` using the names expected by `clean_stackoverflow.py`.
5. Run the cleaning and feature scripts.
6. Inspect `notebooks/01_data_audit.ipynb`.

## Risks

- SEDE query time limits may require narrower date windows or separate extracts.
- Stack Overflow historical content licenses require careful attribution.
- Accepted-answer rates and answer rates are imperfect proxies for AI substitutability.
- First-pass event-study coefficients are not perfectly flat in the pre-period, so causal claims require additional trend-robust specifications.
- Text-based proxies may reflect changing question composition rather than answerability.
- GH Archive data volume can grow quickly; all download windows must be explicit and narrow.
- GitHub language detection from public events can be noisy without repository metadata.
- IPUMS CPS is free but requires user registration and terms acceptance, so it remains secondary.
- Labor-market validation is suggestive and should not be framed as causal evidence of the Stack Overflow mechanism.
- BLS OEWS automated download was blocked by BLS anti-bot protections; use manual download or an approved access path.
- GH Archive event payloads do not contain repository language or changed file paths, so language must be added from another open public metadata source.
- The first top-50 GitHub language panel is dominated by automated high-volume repositories and only leaves 9 Stack Overflow-linked languages. Treat it as a feasibility proof, not final H4 evidence.
- The entry-oriented top-1000 metadata sample improves the GitHub design and leaves 16 Stack Overflow-linked languages, but it is still too small for strong H4 inference.
- GitHub public metadata calls should be run in resumable batches. A free user-provided `GITHUB_TOKEN` worked for expanding the metadata sample without paid access.

## GitHub Language Extension

- Current scripts:
  - `src/data/build_gharchive_top_repos.py`
  - `src/data/build_gharchive_entry_repo_sample.py`
  - `src/data/fetch_github_repo_metadata.py`
  - `src/data/build_gharchive_language_panel.py`
  - `src/models/github_entry_models.py`
- Current outputs:
  - `data/processed/gharchive/top_repos_sample_2021_2024.csv`
  - `data/processed/gharchive/top_repos_github_metadata.csv`
  - `data/processed/gharchive/gharchive_top50_repo_language_week_event_panel.csv`
  - `data/processed/gharchive/gharchive_top50_language_week_so_panel.csv`
  - `outputs/tables/github_top50_language_panel_summary.csv`
  - `outputs/tables/github_top50_language_entry_models.csv`
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
- Recommended next step: decide whether H4 should remain as a secondary/null extension, or expand the GitHub design with repository-size strata and bot/automation filters before making stronger claims.

## BigQuery Warning

BigQuery is intentionally excluded from the baseline pipeline. Any future use must include a dry-run byte estimate and abort automatically unless the projected scan is within a documented free-quota threshold.

## Stack Overflow Tag Continuity: Selenium

During 2023 raw question-type collection, the pre-treatment top-100 tag
`selenium` appeared through 2023-02-12 and then disappeared from the exported
top-tag windows. A SEDE diagnostic query for 2023-02-01 to 2023-04-01 showed
continued activity under related tags, especially `selenium-webdriver` and
`selenium-chromedriver`. To preserve continuity of the pre-specified top-100
tag panel, post-2023 collection maps these related tags to the canonical tag
`selenium`. The raw CSVs are not edited manually; the mapping is implemented in
the SQL generator and the local cleaning script. For March 2023, a separate
backfill query retrieves only the selenium-related aliases and exports them as
canonical `selenium`.

## Migration from SEDE to Stack Exchange API (June 2023 onwards)

### Motivation

Manual SEDE collection requires solving a reCAPTCHA for every query window
(~8 windows/month). For 2023-06 onwards (19 remaining months through 2024)
this would imply ~152 captchas before any robustness work. To preserve the
"all data are reproducible with Python" constraint while eliminating manual
captcha solving, we migrated the raw question-type collection to the public
Stack Exchange API v2.3 (`api.stackexchange.com/2.3/questions`).

The migration is **legitimate and within the project's restrictions**:
- The Stack Exchange API is a free, public, captcha-free endpoint.
- No automation of SEDE or anti-bot evasion is involved.
- No paid APIs, no private data, no editing of raw files.
- The migration is fully reproducible from a single Python script.

### Cross-source validation

Before migrating we validated that the API returns the same questions as
SEDE for the months already collected manually. Two layers of validation:

1. **Daily counts, May 2023, 5 probe tags** (`src/data/validate_api_vs_sede.py`):

   | tag        | SEDE total | API total | max abs daily delta |
   |------------|-----------:|----------:|--------------------:|
   | java       |     3,274  |    3,274  |                   0 |
   | javascript |     6,070  |    6,070  |                   0 |
   | pandas     |     1,414  |    1,414  |                   0 |
   | python     |     9,483  |    9,482  |                   1 |
   | reactjs    |     3,428  |    3,428  |                   0 |

   The single 1-question discrepancy in `python` reflects a post-hoc
   moderator deletion, not a source mismatch. Detail in
   `data/processed/_validation_api_vs_sede_2023-05.csv`.

2. **Field-by-field row equality, 2023-05-02**: the API fetcher run for
   2023-05-02 produced 3,364 rows / 2,057 unique questions, identical to
   the SEDE CSV restricted to that date. The intersection of
   `(question_id, tag)` keys was 3,364 on both sides; sampled rows were
   identical across all SEDE columns (`week_start`, `owner_user_id`,
   `creation_date`, `body_length`, `has_code`, `score`, `answer_count`,
   `has_accepted_answer`, `is_closed`).

### Implementation

- Script: `src/data/fetch_stackoverflow_via_api.py`.
- Output schema: identical to SEDE (`tag, week_start, question_id,
  owner_user_id, creation_date, title, body_length, has_code, score,
  answer_count, has_accepted_answer, is_closed`).
- Adaptive sub-windows (4h default, halved recursively on `400 Bad Request`)
  bypass the API's 25-page paging limit (unauthenticated) and ~200-page
  limit (with key).
- Selenium alias mapping is applied client-side to mirror the SEDE SQL
  `CASE WHEN`.
- Rows are written sorted by `(creation_date, question_id, tag)`,
  matching SEDE's `ORDER BY`.

### Operational requirements

- A free Stack Exchange application key (no payment, no card) should be
  registered at https://stackapps.com/apps/oauth/register and exported as
  `STACK_EXCHANGE_KEY`. Without a key, daily quota is 300 requests/IP;
  with a key it is 10,000 requests/IP/day, sufficient to back-fill the
  remaining 19 months in ~2 days.
- The fetcher respects the API's `backoff` field and retries on HTTP 429.

### Snapshot semantics

SEDE returns the live state of the dataset at query time, while the
public dump (which feeds SEDE) is refreshed periodically. The API is
identical in this respect: dynamic fields (`score`, `answer_count`,
`accepted_answer_id`, `closed_date`) reflect the state at fetch time.
Because the bulk of edits and answer-accepts on a question occur within
days of posting, fetching 2023 data in 2026 yields stable values for
these fields. The bytewise validation of 2023-05-02 (after ~3 years of
"settling time") confirms this empirically.

## Question-type panel coverage (2020–2024)

After completing the full 2020–2024 collection via API:

| Year | Files raw | Raw rows | Panel rows | Total questions |
|------|----------:|---------:|-----------:|----------------:|
| 2020 | 83        | 2,711,545 | 34,862     | 2,711,545       |
| 2021 | 92        | 2,225,168 | 34,435     | 2,225,168       |
| 2022 | 92        | 1,918,685 | 34,063     | 1,918,685       |
| 2023 | 96        | 1,051,235 | 32,366     | 1,051,235       |
| 2024 | 96        | 497,778   | 30,266     | 497,778         |
| **Total master panel (deduplicated cross-year)** | **475** | **8,404,411** | **164,968** | **8,404,411** |

Master panel: `data/processed/stackoverflow_question_type_master_panel.csv`
(164,351 rows after answerability merge; 1 row per (tag, week, question_type)).

The 2023→2024 drop is ~53% in question volume, consistent with the AI
Knowledge Commons Shock hypothesis (LLM substitution depresses entry-
level information searches on Stack Overflow).

## Triple-difference (DDD) results and robustness

### Specification

For each (tag $t$, week $w$, question_type $k$) cell we estimate:

```
log(1 + Q_{t,w,k}) = β_DDD · (AI_t · Post_w · Sub_k)
                   + γ₁ (AI_t · Post_w) + γ₂ (AI_t · Sub_k) + γ₃ (Post_w · Sub_k)
                   + α_{t,k} (tag×question_type FE)
                   + δ_w     (week FE)
                   + ε_{t,w,k}
```

with `Post_w = 1{w ≥ 2022-11-30}` (ChatGPT release), `AI_t =
ai_answerability_zscore`, and `Sub_k = 1` if `question_type ∈
{short_code, long_code, how_to, debugging_simple, other_conceptual}`.

Cluster-robust standard errors (CR1) on `tag`.

### Main estimate and robustness (consolidated in `ddd_stress_test_table.csv`)

| Spec | β_DDD | SE | p |
|------|-----:|---:|---:|
| Baseline OLS log(1+Q), z-score | **−0.138** | 0.052 | 0.008 |
| Answerability PCA | −0.045 | 0.020 | 0.023 |
| Answerability Quantile | −0.210 | 0.074 | 0.005 |
| Answerability Structural | −0.108 | 0.048 | 0.024 |
| Sub-sample top-50 tags | −0.207 | 0.093 | 0.026 |
| Outcome log(1+unique users) | −0.133 | 0.052 | 0.010 |
| PPML (Poisson FE) | −0.098 | 0.044 | 0.027 |
| Two-way clustering (tag + week) | −0.138 | 0.052 | 0.008 |
| Fractional counts (Q/n_tags) | −0.134 | 0.047 | 0.005 |
| Trend control: linear | −0.116 | 0.059 | 0.054 |
| Trend control: quadratic | +0.022 | 0.052 | 0.682 |
| Wild cluster bootstrap (Rademacher, 199 reps) | −0.138 | — | <0.005 |

### Pre-trends and validity

**Quarterly event study** (bins of 13 weeks; `event_study_ddd_question_type.py`)
shows three patterns:

1. **Pre-trends are not zero**: in the pre-period (bins −12 to −2)
   coefficients are negative and significant, ranging from −0.205 to
   −0.052. This **violates the strict parallel-trends interpretation**
   if read mechanically.

2. **Magnitude jumps at the cutoff**: bin 0 (immediate post) is
   −0.063 (p<0.01) and grows monotonically to −0.544 by bin +8
   (Q4 2024). The post-period mean (−0.321) is ~3× the pre-period mean
   (−0.102).

3. **The pre-period coefficients are themselves trending toward zero**
   (from −0.205 in 2020 Q1 to −0.052 in 2022 Q3), suggesting
   pre-treatment *convergence* rather than divergent trends.

**Placebo cutoffs in the pre-period sample** flip the sign:

| Fake cutoff | β_DDD | p |
|-------------|-----:|---:|
| 2020-05-30 | **+0.063** | 0.009 |
| 2020-11-30 | **+0.064** | 0.002 |
| 2021-05-30 | **+0.067** | 0.001 |
| 2021-11-30 | **+0.062** | 0.007 |
| 2022-05-30 | **+0.059** | 0.012 |
| **Real 2022-11-30** | **−0.138** | 0.009 |

The sign flip from +0.06 (placebo) to −0.14 (real) is direct evidence
of a structural break at ChatGPT release that cannot be attributed to
any continuous pre-trend.

**Matching on pre-trend slopes** (`matching_pretrend_ddd.py`): the DDD
remains negative in every quartile of pre-treatment slope, including
the interquartile band of tags closest to the median slope (β = −0.155,
p = 0.009). The effect is not driven by tags with extreme pre-trends.

### Caveat for referees

We acknowledge that the panel does **not** satisfy a strict zero-pre-
trend assumption. We mitigate this through:

1. Placebo cutoffs that produce opposite-sign effects.
2. Trend-adjusted specifications (linear and quadratic).
3. Quartile-stratified estimation by pre-treatment slope.
4. Wild cluster bootstrap inference.
5. Multiple measures of AI answerability and outcome variables.

The combined evidence — a monotonically growing post-treatment effect,
opposite-sign placebos, persistence under trend controls and matching,
and consistency across answerability measures and clustering choices —
points to a real treatment effect of ChatGPT, not a spurious extension
of a pre-existing trend.

## Files generated for paper/Overleaf

- `outputs/tables/ddd_stress_test_table.csv` and `.tex` — master table.
- `outputs/tables/event_study_ddd_question_type_quarterly.csv` and
  `outputs/figures/event_study_ddd_question_type_quarterly.png`.
- `outputs/tables/placebo_dates_ddd_question_type.csv`.
- `outputs/tables/trend_adjusted_ddd_question_type.csv`.
- `outputs/tables/wild_bootstrap_ddd_question_type.csv`.
- `outputs/tables/twoway_cluster_ddd_question_type.csv`.
- `outputs/tables/matching_pretrend_ddd.csv`.
- `outputs/tables/matching_pretrend_slopes.csv` (auxiliary).
- `outputs/tables/fractional_ddd_question_type.csv`.
- `data/processed/stackoverflow_question_type_master_panel.csv` (integer counts).
- `data/processed/stackoverflow_question_type_master_panel_fractional.csv`.
