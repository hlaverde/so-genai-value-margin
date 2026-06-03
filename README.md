# The Post-ChatGPT Contraction Reaches the Crowd-Validated Margin

**A Within-Tag Triple Difference and a Value-Calibrated Early-Warning System for Stack Overflow**

Authors: **Henry Laverde-Rojas** and **Carlos Laverde-Rodriguez**
Programa de Economía, Universidad Militar Nueva Granada, Campus, Colombia.

---

## What this repository is

This is the **public replication package** (a research-data and code
archive) for the paper above. **It is not journal supplementary
material.** All evidence necessary to evaluate the main claims is
reported in the article itself; this repository exists for
transparency, replication, auditability, and the extended robustness
outputs that do not fit the article's page budget.

## Project description

Generative AI has contracted public question-and-answer activity on
Stack Overflow. A *benign-pruning* reading holds that it removes only
low-value posts. Using a primary 2020–2024 panel of 8.4 million Stack
Overflow questions across 100 top pre-treatment tags and 261 weeks,
plus a full 100-tag 2025 validation extension, the paper estimates a
within-tag triple difference at the (tag × week × question-type) cell
and shows that the displacement **reaches the crowd-validated margin**,
not only score-zero posts. The empirical result is turned into a
**value-calibrated early-warning system**: a reproducible
scoring-and-alerting artefact that supports budget-constrained
allocation of intervention effort, validated out of sample by
detection AUC, budgeted regret relative to a perfect-foresight oracle,
and 2025 persistence.

## Data availability

- **Sources:** the public Stack Exchange Data Explorer (SEDE) browser
  interface (through May 2023) and the public Stack Exchange API v2.3
  (from June 2023, including the 2025 extension). Both are free; the
  API requires only a registered application key.
- **Raw user-generated content is not redistributed.** Stack Overflow
  content is licensed CC BY-SA 4.0; this repository distributes only
  derived statistics, code, and audit logs.
- **Regeneration:** scripts under `src/` rebuild every derived table
  from public sources. See `docs/DATA_AVAILABILITY.md` and
  `docs/REPLICATION_GUIDE.md`.

## Reproducibility

```bash
# 1. Environment (Python 3.11+)
python -m venv .venv
# Windows:  .venv/Scripts/activate
# Unix:     source .venv/bin/activate
pip install -r requirements.txt

# 2. Provide a free Stack Exchange API key (no payment required)
cp .env.example .env          # then edit .env and set:
# STACKEXCHANGE_KEY=your_key_here

# 3. Fetch the 2025 validation extension (all 100 tags)
python src/data/fetch_2025_extension.py

# 4. Build the clean question-tag data and the analysis panel
python -m src.data.clean_stackoverflow
python -m src.features.build_ai_answerability

# 5. Validate the question-type taxonomy (three classifiers)
python src/analysis/validate_question_type_strong.py

# 6. Run the main analyses
python src/analysis/27_full_2025_estimation.py   # DDD + event study
python src/analysis/26_dss_referee_fixes.py      # shape test + VOI/regret
python src/analysis/28_full_2025_monitor.py      # early-warning + persistence
```

Exact commands and expected outputs are documented in
`docs/REPLICATION_GUIDE.md`. Forward slashes work on Windows
PowerShell.

## Main outputs

- Within-tag triple-difference (DDD) estimates and the co-primary
  embedding-based treatment.
- Quarterly event study (2020–2024 main panel and 2020–2025 extension).
- Value-margin **shape test** (the C1 benign-pruning test).
- DSS **early-warning / VOI–regret** tables (detection AUC, budgeted
  regret relative to the oracle, composition-flag persistence).
- 2025 collection **audit** (per-tag coverage, 0 failed windows,
  0 page-cap flags).

## Repository layout

```text
paper/      LaTeX source, bibliography, figures, and tables of the article
src/        reproducible Python pipeline (data, features, models, analysis)
sql/        Stack Exchange Data Explorer queries
docs/       data, variable, identification, replication, and audit notes
tests/      smoke tests on simulated data
notebooks/  audit and exploration notebooks
outputs/    generated tables, figures, model summaries, and audit logs
```

Raw and large derived data are not tracked (see `.gitignore`); they are
regenerated from public sources by the scripts above.

## License

- **Code:** MIT (see `LICENSE`).
- **Derived data and outputs:** released for replication only.
- **Stack Overflow content:** CC BY-SA 4.0; underlying user-generated
  content is **not** redistributed here.

## Citation

Manuscript (under review; update on acceptance):

> Laverde-Rojas, H., & Laverde-Rodriguez, C. (2026). *The Post-ChatGPT
> Contraction Reaches the Crowd-Validated Margin: A Within-Tag Triple
> Difference and a Value-Calibrated Early-Warning System for Stack
> Overflow.* Working paper.

Repository: see `CITATION.cff`. Preferred URL:
`https://github.com/hlaverde/so-genai-value-margin`
