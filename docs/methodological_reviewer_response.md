# Methodological Reviewer Response Matrix

This note tracks the non-scope revisions made in response to the DSS-style
major-revision memo. The journal-fit/reframing issue is intentionally excluded
from this file.

## Resolved in Current Revision

| Reviewer concern | Action taken | Files |
|---|---|---|
| AI-answerability may measure popularity/maturity rather than LLM answerability. | Added revealed-answerability validation based only on pre-ChatGPT objective resolution signals. Added LaTeX table and manuscript discussion. Existing embedding validation and partial-regression table retained. | `src/features/validate_ai_answerability_revealed.py`; `paper/tables/table_revealed_answerability_validation.tex`; `paper/sections/data.tex` |
| Structural AI-answerability proxy is only moderately correlated with embedding validation. | Added a direct DDD re-estimation using the embedding-based tag answerability score as treatment. Result: beta = -0.1188, p < 0.001. Reframed the embedding treatment as a co-primary measurement check. | `src/analysis/16_embedding_answerability_treatment.py`; `paper/tables/table_embedding_answerability_treatment.tex`; `paper/sections/data.tex`; `paper/sections/results_ddd_question_type.tex` |
| Binary substitutability has moderate agreement, not strong agreement. | Changed language from "moderate-to-substantial" to "moderate"; reframed binary classifier as funnel-building baseline and continuous embedding score as co-primary measurement check. | `paper/sections/validation_question_type.tex`; `paper/sections/robustness.tex`; `paper/sections/results_ddd_question_type.tex` |
| Pre-trends are not flat and HonestDiD breakdown at M=0.75 weakens causal confidence. | Added formal pre-trend diagnostics table, explicitly reporting rejections of exact parallel trends; revised identification language to "moderate" and "quasi-causal"; corrected HonestDiD text to full-VCV M=0.75. | `paper/tables/table_formal_pretrend_diagnostics.tex`; `paper/sections/identification.tex`; `paper/sections/limitations.tex`; `paper/tables/table_honestdid_bounds.tex` |
| Placebo sign reversal was overstated as proof. | Rewrote placebo interpretation as supportive/informative but not proof of parallel trends. | `paper/sections/results_ddd_question_type.tex`; `paper/sections/identification.tex`; `paper/sections/conclusion.tex` |
| High-value artefact result overclaims because score >= 5 is null. | Added mutually exclusive score-bin analysis and figure, plus an approximate 80%-power MDE column. Revised text to state that score >= 5 is underpowered/inconclusive, not protected. | `src/analysis/15_score_bin_artefact_effects.py`; `paper/tables/table_score_bin_artefact_effects.tex`; `paper/figures/fig_score_bin_artefact_effects.pdf`; `paper/sections/results_ddd_question_type.tex`; `paper/main.tex`; `paper/sections/introduction.tex` |
| Language implied stronger causality than design warrants. | Replaced several direct causal claims with conditional/quasi-causal language; emphasized maintained parallel-trends assumption and non-random treatment intensity. | `paper/sections/identification.tex`; `paper/sections/results.tex`; `paper/sections/mechanisms.tex`; `paper/sections/conclusion.tex`; `paper/main.tex` |
| Old limitation said HonestDiD full machinery was not implemented. | Updated limitation: full-VCV HonestDiD is now implemented; conclusion is moderate, not strong. | `paper/sections/limitations.tex` |
| Funnel terminology implied durable reuse without observing reuse. | Renamed the main object in the manuscript to "funnel-qualified posts" / "support-post funnel"; removed "reusable knowledge artefact" language from the abstract, tables, results, and conclusion. | `paper/main.tex`; `paper/sections/results_ddd_question_type.tex`; `paper/tables/table_reusable_funnel.tex`; `paper/tables/table_value_weighted_funnel.tex`; `paper/tables/table_decline_decomposition.tex` |
| GH-Archive appendix was non-informative. | Removed the GH-Archive appendix from `main.tex` and deleted its paper source file. The exploratory exercise is now described only as not reported/non-informative in data and limitations. | `paper/main.tex`; `paper/sections/data.tex`; `paper/sections/limitations.tex`; deleted `paper/sections/appendix_github.tex` |
| Practical implications were too generic. | Replaced the generic decision matrix with implementable monitoring/routing rules and thresholds, including top-quartile AI score > 0.34, closed-share alert > 0.01, and score-bin monitoring. | `paper/sections/policy_implications.tex` |

## Still Not Fully Resolved

| Concern | Current position |
|---|---|
| Direct GPT-4o/LLM validation of answerability. | Not implemented because it would violate the zero-budget/no-paid-API constraint and embed a specific model generation into the treatment. Current alternative: embedding validation, embedding-treatment DDD, and objective revealed-answerability validation. |
| Causal certainty. | Not claimed. The revised manuscript now frames evidence as a conditional quasi-causal estimate under explicit assumptions. |
| New-user mechanism. | Still not solved in this revision; requires user-post-level data not present in the current tag-week-question-type panel. |
| GitHub downstream mechanism. | Removed from the reported paper. It should not be used as a central pipeline claim unless redesigned at repo-week level. |

## Verification

The paper compiles successfully with:

```powershell
cd "D:\DocumentosHL\Documentos\Documents\2021\Henry Laverde\2026\Investigación\Paper de IA\Propuesta No. 1\ai-knowledge-commons-shock\paper"
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

Current output:

`paper/main.pdf`
