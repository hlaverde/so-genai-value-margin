# AI Answerability Coding Codebook

This codebook is for validating the tag-level AI-answerability treatment using question-level coding.

Coders should not use the tag-level AI score or stratum. The coding files are intentionally blind.

## Unit

One Stack Overflow question.

## Coding Variables

Use `1` for yes and `0` for no. Leave blank only if the item cannot be judged.

### `human_ai_answerable`

Would a general-purpose generative AI assistant likely produce a useful answer from the question alone, without complex external context?

Code `1` if:

- the question is self-contained;
- the requested task is a common programming, syntax, API, data manipulation, or debugging issue;
- a model could provide a plausible actionable answer from the title/body/code.

Code `0` if:

- the question depends on hidden local files, credentials, deployment state, private data, or interactive diagnosis;
- the answer requires project-specific architecture decisions;
- the question is ambiguous or underspecified.

### `basic_howto_debugging`

Code `1` if the question is a basic how-to, syntax, simple debugging, common error, or short-code task.

### `requires_context`

Code `1` if the question requires substantial external or local context, such as exact environment, version conflicts, private data, logs not shown, business rules, or system architecture.

### `sufficient_information`

Code `1` if the question includes enough information for a knowledgeable assistant to attempt a useful answer.

### `llm_ai_answerable`

Use this when a coder explicitly asks an LLM or simulates an LLM classification. Code `1` if the LLM judges the question answerable. If no LLM coding is done, leave blank.

### `confidence_1_to_5`

Coder confidence:

- 1 = very uncertain
- 2 = uncertain
- 3 = moderate
- 4 = confident
- 5 = very confident

## Recommended Workflow

1. Code the pilot file first.
2. Compare coders and refine rules.
3. Then code the full file.
4. Save each coder's completed file separately, for example:
   - `ai_answerability_validation_pilot_coder_A.csv`
   - `ai_answerability_validation_pilot_coder_B.csv`
   - `ai_answerability_validation_full_coder_A.csv`
   - `ai_answerability_validation_full_coder_B.csv`

## Validation Metrics

The scoring script computes:

- correlation between tag-level index and human answerability share;
- correlation between tag-level index and LLM answerability share;
- Spearman rank correlation;
- AUC for high-answerability classification;
- Cohen's kappa or Fleiss' kappa across coders.
