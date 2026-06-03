# Cover letter — Decision Support Systems

**Manuscript:** *The Post-ChatGPT Contraction Reaches the Crowd-Validated
Margin: A Within-Tag Triple Difference and a Value-Calibrated
Early-Warning System for Stack Overflow*

**Authors:** Henry Laverde-Rojas; Carlos Laverde-Rodriguez
(Programa de Economía, Universidad Militar Nueva Granada, Campus, Colombia)

---

Dear Editors,

We are pleased to submit the manuscript above for consideration at
*Decision Support Systems*.

**Fit with the journal.** The paper's core deliverable is a decision
aid, evaluated as one. Platform managers (and AI providers monitoring
the health of their training corpus) face a concrete, budget-constrained
decision: as public knowledge production erodes after ChatGPT, where
should scarce intervention effort—contributor incentives, attribution
mechanisms, moderation attention—be allocated? We build a
**value-calibrated early-warning system** that answers this from signals
a platform already collects, and we assess it the way a decision-support
tool should be assessed: by out-of-sample detection performance and by a
value-of-information / regret analysis against a perfect-foresight
benchmark. This is squarely the journal's remit—analytics and AI in
support of managerial decisions, with an explicit account of the
decision the tool improves and the loss it averts.

**The artefact.** The system separates two layers. Detection runs on the
activity-decline signal a platform already tracks (out-of-sample
AUC 0.98 for locating where 2025 high-value erosion is largest). The
contribution is the **calibration** layer: the paper's within-tag
value-margin estimates convert an activity alert into the
decision-relevant quantity managers lack—the high-value posts at risk.
Allocating a fixed intervention budget by the calibrated
high-value-at-risk nearly attains the perfect-foresight optimum
(calibrated regret under 1%), whereas allocating by raw activity leaves
3–5% of the protectable high-value flow unprotected. A persistent
composition flag (ρ = 0.90 into the new 2025 data) classifies which
declines are value-disproportionate, informing the *type* of
intervention. The artefact is a reproducible scoring-and-alerting
procedure; production deployment and a manager usability study are
outside the scope of this paper and identified as future work.

**Empirical contribution.** Using a primary 2020–2024 panel of 8.4
million Stack Overflow questions (100 top tags, 261 weeks) and a full
100-tag 2025 validation extension, a pre-specified shape test shows that
the post-ChatGPT contraction **reaches the crowd-validated margin**
(average displacement −0.167, p < 1e-4), not only score-zero posts—so
the benign-pruning reading of the surviving-quality literature does not
hold at the within-tag value margin.

**Scope, stated plainly.** Exact parallel trends are rejected; we
therefore present a conditional post-ChatGPT association aligned with the
LLM-substitutability mechanism, whose credibility rests on a convergence
of diagnostics (placebo sign-reversal, pre-trend matching, a 32-cell
specification curve, a donut difference-in-differences, a HonestDiD
breakdown at M̄ = 0.75) and on the full 2025 extension, which strengthens
the estimate to −0.172 (p = 0.002) and deepens to −0.68 with no
reversion—most consistent with sustained diffusion. The estimate speaks
to the public Q&A replenishment margin, not to welfare or
innovation-output claims.

**Reproducibility.** All evidence needed to evaluate the main claims is
in the article. A public replication package (a research-data and code
archive) provides the code, data-construction scripts, audit logs,
derived tables, and extended robustness outputs, reproducible from
public, zero-budget sources.

The manuscript is original, is not under consideration elsewhere, and
both authors have approved the submission. We thank you for your
consideration.

Sincerely,
Henry Laverde-Rojas and Carlos Laverde-Rodriguez

---

*Replication repository:* <https://github.com/hlaverde/so-genai-value-margin>
