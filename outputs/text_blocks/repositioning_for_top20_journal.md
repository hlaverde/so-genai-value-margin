# Repositioning bloques para el manuscrito v8

_Bloques listos para pegar en `paper/main.tex` o equivalente. Lenguaje prudente
(no causal-strong, no welfare claims). Citas de Xue, Burtch, del Rio-Chanona,
Quinn-Gutt, Shan-Qiu están a nivel parentético; ajustar al estilo de Research
Policy. Cifras concretas referidas a la run del 2026-05-26._

---

## BLOQUE A — Gap en la literatura (intro, ~120 palabras)

A growing empirical literature has documented that the release of ChatGPT was
followed by a sharp decline in user-generated activity on programming Q&A
platforms, with Xue et al. (2026) reporting a 14.09% reduction in weekly
question posts on Stack Overflow (reaching 27.88% by May 2023), Burtch et al.
(2024) finding analogous declines on Stack Exchange more broadly, and del
Rio-Chanona et al. (2024) showing how the contraction varies by topical
exposure to LLM substitution. These studies consistently characterise the
shock as a *change in platform activity*: fewer questions, fewer (and on
several margins higher-quality) survivors, and changes in user retention,
answer dynamics, and content composition. What this literature has not yet
addressed is whether the same task-level LLM-substitutability margin that
displaces *platform activity* also displaces the production of *reusable
public knowledge artefacts*—the durable, accepted, non-closed, non-negative
answers that are the actual stock of value the commons accumulates.

---

## BLOQUE B — Research question (intro, ~70 palabras)

This paper asks a different question from the existing displacement
literature. Conditional on the task-level LLM-substitutability margin
identified in our triple-difference design, what fraction of the shock
translates into lost *reusable knowledge artefacts* (accepted answers with
non-negative score on non-closed questions) versus lost *platform activity*?
And what share of the aggregate post-ChatGPT decline is causally attributable
to the DDD-identified channel, as opposed to co-occurring secular, policy,
and macro forces?

---

## BLOQUE C — Contribution (intro or section 1.2, ~150 palabras)

We make three contributions that complement, rather than replicate, the
existing displacement literature. First, building on the task-level
substitutability framework operationalised in our prior work and validated
against three independent classifiers (Fleiss κ = 0.52), we trace the same
triple-difference effect through a five-stage knowledge-production funnel:
from raw questions through answered, accepted, accepted-and-non-closed,
accepted-with-non-negative-score, down to *reusable artefacts*. Second, we
provide a formal decomposition of the post-ChatGPT decline into the
DDD-identified channel and a residual that captures secular, policy, and
macro forces; the DDD channel is bounded at ≈5% of the aggregate trend-implied
shortfall in questions and ≈5.6% of the shortfall in reusable artefacts.
Third, conditional on tag × question-type and week fixed effects, we find
that the apparent improvement in resolvability of survivors reported in
recent work does not survive the inclusion of fine-grained composition
controls, with closed-share rising marginally (β = +0.005, p < 0.001).
Together these results suggest that *platform activity is not the same as
reusable knowledge production*, and that the displacement-via-LLMs channel
is real but bounded.

---

## BLOQUE D — Hipótesis H5 (sección de marco teórico, ~90 palabras)

**H5 (Reusable artefact funnel).** If LLMs substitute primarily for
*platform activity* but not for the cognitive and curation work that converts
a question into a durable, accepted, non-closed, non-negative artefact, the
relative DDD effect should be similar across funnel stages, but the absolute
implied displacement in reusable artefacts should be a small fraction of the
implied displacement in raw questions. Equivalently, the post-ChatGPT
shortfall in reusable knowledge production should be smaller—not larger—in
absolute terms than the shortfall in raw activity, despite a comparable
relative effect size.

---

## BLOQUE E — Hipótesis H6 (sección de descomposición, ~70 palabras)

**H6 (Bounded channel).** The DDD-identified marginal channel
(AI × Sub × Post) explains a bounded share of the aggregate post-ChatGPT
decline. Specifically, after extrapolating a pre-period log-linear trend to
the 109-week post window, the DDD-implied displacement should account for at
most 10% of the trend-implied shortfall in both raw questions and reusable
artefacts. The remainder reflects secular pre-trends, policy changes (e.g.,
Stack Overflow's moderation actions, AI-content bans, model rate limits),
and macro shocks (return-to-work, advertising market, developer-tool
substitution) that lie outside the identification strategy.

---

## BLOQUE F — Conclusion paragraph aligning H5–H6 with the new results
(~110 palabras)

Consistent with H5, we observe stable relative DDD effects across the funnel
(β between −0.108 and −0.121, all p < 0.025), but a sharp attenuation in
absolute terms: the implied displacement falls from ~70,000 questions to
~28,000 reusable artefacts (about 40% of the platform-activity shock).
Consistent with H6, the DDD-identified channel accounts for ≈5.0% of the
trend-implied shortfall in raw questions and ≈5.6% of the shortfall in
reusable artefacts during the 109-week post window. The remainder—roughly
1.35 million questions and 469,000 reusable artefacts—is residual: it is
*not* attributable, with our design, to the marginal LLM-substitutability
margin. These bounds suggest a substantially more modest causal role for
LLM displacement than aggregate descriptive statistics would imply.

---

## BLOQUE G — Sentencia de mensaje único (resumen ejecutivo o abstract revision)

> _"Existing work documents that ChatGPT reduced Stack Overflow activity and
> changed quality, novelty, readability, user composition, and answer
> dynamics. This paper asks a different question: whether the task-level
> LLM-substitutability margin reduces mere platform activity or the
> production of reusable public programming-knowledge artefacts.
> Tracing a five-stage funnel from questions to reusable artefacts and
> decomposing the aggregate post-ChatGPT decline, we find that (i) the
> relative DDD effect is stable across funnel stages but the absolute
> displacement in reusable artefacts is roughly 40% of that in raw
> activity, and (ii) the DDD-identified channel accounts for only
> ~5% of the aggregate trend-implied shortfall. Platform activity is not
> the same as reusable knowledge."_

---

## Citas a comprobar antes de enviar

- **Xue et al. (2026)** — verificar journal y página exacta. Abstract usado:
  14.09% reducción, 27.88% por mayo 2023, mecanismos uneven substitution +
  quality spillover.
- **Burtch et al. (2024)** — actualizar a la versión publicada (vs working
  paper); validar el % de declive reportado.
- **del Rio-Chanona et al. (2024)** — PNAS Nexus, validar año/volumen.
- **Quinn–Gutt (2024)** — verificar título exacto y venue.
- **Shan–Qiu (2024 or 2025)** — verificar idem.
- **Rambachan–Roth** (Honest-DiD) — ya está en bibliografía v7.
- **Sun–Abraham** (heterogeneity-robust event study) — ya está en bibliografía v7.

---

## Notas para el cover letter (v8)

- Recordar al editor que el paper v7 ya está sólido en identificación y
  honesto en magnitud (~4%); v8 añade **tres extensiones empíricas
  diferenciadoras** (funnel, decomposition, descriptive vs conditional
  quality contrast).
- Enfatizar que el reusable funnel y la descomposition channel-vs-residual
  son **novedad metodológica**, no presentes en Xue/Burtch/del Rio-Chanona.
- Lenguaje: "bounded channel", "task-level margin", "platform activity ≠
  reusable knowledge". Evitar "kills", "destroys", "innovation effect".
