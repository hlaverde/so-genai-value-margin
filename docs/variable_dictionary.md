# Variable Dictionary

## Stack Overflow Tag-Week Panel

- `tag`: Stack Overflow tag name.
- `week_start`: Monday week start date.
- `questions`: number of question posts.
- `answers`: number of answer posts linked to questions in the tag.
- `accepted_answers`: count of questions with a non-null accepted answer.
- `answer_rate`: share of questions with at least one answer.
- `avg_score`: mean question score.
- `closed_questions`: count of questions with non-null `ClosedDate`.
- `unique_users`: distinct question owners.
- `post_chatgpt`: indicator equal to one for weeks starting on or after 2022-11-30.

## User-Tag-Week Panel

- `user_id`: Stack Overflow owner user id.
- `tag`: Stack Overflow tag name.
- `week_start`: Monday week start date.
- `reputation_initial`: user reputation measured in the source extract.
- `user_age_days`: days between user account creation and the week start.
- `posts`: total posts by the user in the tag-week.
- `questions`: question posts by the user in the tag-week.
- `answers`: answer posts by the user in the tag-week.
- `new_user`: indicator for users below a configurable account-age threshold.
- `low_reputation_user`: indicator for users below a configurable reputation threshold.

## Post Complexity

- `post_id`: Stack Overflow post id.
- `tag`: tag name; one row per post-tag pair when tags are exploded.
- `creation_date`: post creation timestamp.
- `body_length`: character length of post body.
- `has_code`: indicator for `<code>` or fenced-code-like content.
- `num_tags`: number of tags on the question.
- `answer_count`: number of answers recorded on the question.
- `has_accepted_answer`: indicator for non-null accepted answer id.
- `score`: post score.
- `short_code_question`: indicator for posts with code and a short body.
- `how_to_question`: simple text indicator for questions containing how-to language.

## AI Answerability

- `accepted_answer_rate_pre`: pre-ChatGPT accepted-answer rate.
- `answer_rate_pre`: pre-ChatGPT answer rate.
- `short_code_share_pre`: pre-ChatGPT share of short code questions.
- `how_to_share_pre`: pre-ChatGPT share of how-to questions.
- `historical_frequency_pre`: pre-ChatGPT number of questions.
- `tag_maturity_weeks_pre`: number of active pre-ChatGPT weeks.
- `ai_answerability_zscore`: average z-scored index.
- `ai_answerability_pca`: first principal component index.
- `ai_answerability_quantile`: quantile-rank index.
- `ai_answerability_structural`: conservative non-text index.
