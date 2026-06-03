# Data Availability

All evidence necessary to evaluate the main claims of the paper is
reported in the article. This repository is a research-data and code
archive (a public replication package), **not** journal supplementary
material.

## Sources

| Source | Coverage | Access |
|---|---|---|
| Stack Exchange Data Explorer (SEDE) | through 2023-05 | Free public browser interface; SQL in `sql/` pasted manually |
| Stack Exchange API v2.3 | 2023-06 onward, incl. full 2025 | Free public endpoint; requires a registered application key (no payment) |

The two sources were validated byte-for-byte on the May 2023 overlap
(identical across every metadata column).

## What is and is not redistributed

- **Not redistributed:** raw Stack Overflow user-generated content
  (question/answer bodies and per-user records). Stack Overflow content
  is licensed CC BY-SA 4.0; redistribution of bulk raw content is out of
  scope for this archive.
- **Provided:** all code and SQL; derived, aggregated statistics at the
  (tag, week, question-type) cell level used in the article; audit logs
  of the 2025 collection; derived tables and figures; and the scripts
  needed to regenerate every input from the public sources above.

## Regenerating the data

Raw and large derived panels are **not** tracked by git (see
`.gitignore`). They are reproducible from public sources:

1. Set a free Stack Exchange API key in `.env` (`STACKEXCHANGE_KEY`).
2. Run the SEDE queries in `sql/` for the pre-2023-06 window (manual,
   documented in `docs/stackoverflow_sede_download.md`), or rely on the
   API path for the full window.
3. Run `python src/data/fetch_2025_extension.py` for the 2025 extension.
4. Run the cleaning and feature scripts in `src/` to rebuild the
   analysis panel (`docs/REPLICATION_GUIDE.md` lists exact commands).

## Audit

The 2025 collection is fully audited: 100/100 tags, 0 failed windows,
0 page-cap flags, 87,027 unique 2025 questions; the combined 2020–2025
panel has 186,188 (tag, week, question-type) cells and reproduces the
original panel exactly for weeks before 2024-12-30. Audit outputs are
under `outputs/` and `docs/`.
