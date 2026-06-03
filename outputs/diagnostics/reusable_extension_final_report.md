# Reusable Artifact Funnel Extension - Final Report

_Generated: 2026-05-26T11:54:40_

## 1. Resumen ejecutivo

Este reporte documenta la ejecucion end-to-end de la extension del manuscrito v7 hacia v8, agregando tres bloques empiricos diferenciadores: (i) un *reusable artifact funnel* de cinco etapas, (ii) un contraste resolvability vs quality, y (iii) una descomposicion del declive agregado entre el canal DDD identificado y el residual.

## 2. Resultados principales

### 2.1 Funnel DDD

- Baseline (questions_count) beta_DDD = **-0.1082** (SE 0.0460, p=0.0206). Coincide con baseline v7 publicado (-0.108).
- Reusable artifact beta_DDD = **-0.1183** (SE 0.0487, p=0.0169).
- Implied displacement: questions = **70,364** vs reusable artifacts = **28,001** (reusable ~ 40% del impacto sobre volumen).

### 2.2 Resolvability vs quality

- Accepted share: beta=-0.0030, SE=0.0040, p=0.4460
- Answered share: beta=-0.0007, SE=0.0038, p=0.8539
- Unanswered share: beta=+0.0007, SE=0.0038, p=0.8539
- No-accepted share: beta=+0.0030, SE=0.0040, p=0.4460
- **Closed share: beta=+0.0049, SE=0.0012, p=0.0001**
- Mean answer count: beta=-0.0063, SE=0.0077, p=0.4135

_Lectura: cuando controlamos por FE tag x qtype y week, las shares de resolvability/quality no responden significativamente al shock; el unico cambio significativo es un aumento marginal en closed_share (+0.005, p<0.001). Esto **matiza** la lectura de Xue et al. (2026) de que la calidad de las preguntas remanentes mejora; bajo controles fine-grained ese efecto no aparece._

### 2.3 Decline decomposition

- Trend-implied shortfall (questions): **1,418,907** en 109 semanas post.
- DDD-identified channel (questions): **70,364** = 5.0% del shortfall.
- Trend-implied shortfall (reusable): **496,715**.
- DDD-identified channel (reusable): **28,001** = 5.6% del shortfall.

_Lectura: el canal causalmente identificado por el DDD es **bounded**; explica ~5-6% del declive agregado, dejando el grueso a tendencia secular, politica de plataforma y macro._

## 3. Pipeline run log

| # | Step | Status | Elapsed (s) |
|---|------|--------|-------------|
| 1 | Bloque 0 - Diagnostico de schema | PASS | 2.4 |
| 2 | Bloque 1 - Build funnel panel | PASS | 56.7 |
| 3 | Bloque 2 - DDD por outcome | PASS | 33.3 |
| 4 | Bloque 3 - Resolvability vs quality | PASS | 40.9 |
| 5 | Bloque 4 - Decline decomposition | PASS | 4.2 |
| 6 | Bloque 6 - Validacion final | PASS | 3.0 |

## 4. Outputs presentes

- [PRESENT] `data\processed\reusable_artifact_funnel_panel.csv` (19832.4 KB)
- [PRESENT] `data\processed\resolvability_panel.csv` (43950.8 KB)
- [PRESENT] `outputs\models\reusable_funnel_ddd_results.csv` (1.1 KB)
- [PRESENT] `outputs\models\resolvability_ddd_results.csv` (0.9 KB)
- [PRESENT] `outputs\models\decline_decomposition.csv` (0.6 KB)
- [PRESENT] `outputs\tables\table_reusable_funnel.tex` (1.2 KB)
- [PRESENT] `outputs\tables\table_resolvability_vs_quality.tex` (0.9 KB)
- [PRESENT] `outputs\tables\table_prepost_resolvability_by_ai_group.tex` (1.1 KB)
- [PRESENT] `outputs\tables\table_decline_decomposition.tex` (1.0 KB)
- [PRESENT] `outputs\tables\table_literature_positioning.tex` (1.4 KB)
- [PRESENT] `outputs\figures\fig_reusable_funnel_coefficients.pdf` (19.8 KB)
- [PRESENT] `outputs\figures\fig_resolvability_coefficients.pdf` (20.0 KB)
- [PRESENT] `outputs\figures\fig_decline_decomposition.pdf` (26.7 KB)
- [PRESENT] `outputs\text_blocks\repositioning_for_top20_journal.md` (7.7 KB)
- [PRESENT] `outputs\diagnostics\reusable_artifacts_schema_report.md` (21.8 KB)
- [PRESENT] `outputs\diagnostics\reusable_funnel_build_audit.md` (4.2 KB)
- [PRESENT] `outputs\diagnostics\reusable_extension_validation_report.md` (1.7 KB)

## 5. Limitaciones (incluir en el paper)

- La descomposicion canal-vs-residual depende de la especificacion log-linear pre-trend. Sensibilidades alternativas (cuadratica, Prais-Winsten, structural break tests) deberian acompañar la version final.
- El clasificador question_type (regex + heuristicas; Fleiss kappa = 0.52 vs tres clasificadores independientes) es moderado, no perfecto; resultados son robustos al swap por embedding-only.
- El periodo post (109 semanas) cubre la difusion temprana de ChatGPT, GPT-4 y Copilot; no separa estos shocks de manera causal.
- La definicion `reusable_artifact = accepted & score>=0 & not closed` es una proxy razonable de durabilidad pero no captura toda la dimension de utilidad (vistas, citas en otros sites, etc.).
- No tenemos contrafactual para el residual; el 95% no se atribuye al shock LLM solo porque el DDD no lo identifica como tal.

## 6. Lenguaje prudente para el paper

Usar: "consistent with", "suggests", "bounded channel", "platform activity is not the same as reusable knowledge".
Evitar: "proves", "kills", "destroys", "innovation effect", "welfare effect", "causal mechanism" (sin matizacion).