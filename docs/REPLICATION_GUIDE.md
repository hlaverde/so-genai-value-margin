# Replication Guide

This guide reproduces the analysis end-to-end from public, zero-budget
sources. Forward slashes work on Windows PowerShell and on Unix.

## 0. Environment

```bash
python -m venv .venv
# Windows:  .venv/Scripts/activate
# Unix:     source .venv/bin/activate
pip install -r requirements.txt
```

Python 3.11+ is assumed.

## 1. Credentials

The only credential is a **free** Stack Exchange API application key
(no payment, no credit card). Register one at
<https://stackapps.com/apps/oauth/register> and place it in `.env`:

```bash
cp .env.example .env
# edit .env:
# STACKEXCHANGE_KEY=your_key_here
```

The key is read from the environment; it is never committed
(`.env` is git-ignored).

## 2. Data construction

| Step | Command | Output |
|---|---|---|
| Pre-2023-06 (SEDE) | run the SQL in `sql/` manually (see `docs/stackoverflow_sede_download.md`) | raw CSVs in `data/raw/stackoverflow/` |
| 2023-06 onward (API) | `python src/data/fetch_stackoverflow_via_api.py` | raw CSVs in `data/raw/stackoverflow/` |
| 2025 extension | `python src/data/fetch_2025_extension.py` | 2025 raw + audit logs |
| Clean | `python -m src.data.clean_stackoverflow` | `data/interim/` |
| Features / panel | `python -m src.features.build_ai_answerability` | `data/processed/` analysis panel |

Raw and processed data are not tracked by git; the steps above
regenerate them from public sources.

## 3. Validation

```bash
python src/analysis/validate_question_type_strong.py   # 3-classifier kappa
pytest                                                  # smoke tests on simulated data
```

## 4. Main analyses

| Result | Command |
|---|---|
| Baseline DDD + co-primary embedding treatment | `src/models/` DDD scripts |
| Quarterly event study + 2025 extension | `python src/analysis/27_full_2025_estimation.py` |
| Value-margin shape test (C1) + VOI/regret | `python src/analysis/26_dss_referee_fixes.py` |
| Early-warning system + 2025 persistence | `python src/analysis/28_full_2025_monitor.py` |

## 5. Expected headline numbers (sanity gate)

- Baseline DDD: **−0.108** (p = 0.021); embedding co-primary **−0.119**.
- Boundary-excluded: **−0.140** (p = 0.005).
- Shape test: average **−0.167** (p < 1e-4), slope −0.094 (p = 2e-4).
- Full 2020–2025 panel: **−0.172** (p = 0.002); event study to −0.68.
- Early-warning: detection AUC **0.98** vs 0.57; calibrated regret
  under 1% vs 3–5% naive; composition-flag persistence ρ = 0.90.

If the baseline DDD does not reproduce **−0.108**, stop and check the
panel construction before interpreting downstream results.

## 6. Build the manuscript

```bash
cd paper
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```
