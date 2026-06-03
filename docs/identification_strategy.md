# Identification Strategy

## Core Shock

The treatment date is the public release of ChatGPT on 2022-11-30. The maintained empirical interpretation is an information-environment shock: generative AI made private, conversational programming help widely available at near-zero marginal cost.

## Treatment Intensity

The main treatment intensity is `AI_Answerability`, measured at the Stack Overflow tag level using only pre-ChatGPT data. The index is intended to capture how easily a tag's historical questions could be substituted by generative AI answers.

Planned versions:

1. Z-score average across structural and text-light proxies.
2. First principal component.
3. Quantile-rank index.
4. Conservative structural index excluding text-derived variables.

## Main Stack Overflow DID

```text
Y_tw = alpha_t + lambda_w + beta * (AI_Answerability_t x PostChatGPT_w) + epsilon_tw
```

Where `t` indexes tags and `w` indexes weeks. Outcomes include questions, answers, accepted answers, answer rates, votes, closure rates, new-user activity, and post complexity.

## Event Study

```text
Y_tw = alpha_t + lambda_w + sum_k beta_k * (AI_Answerability_t x 1[relative_week = k]) + epsilon_tw
```

The event study is used to assess pre-trends and dynamic adjustment after 2022-11-30.

## User Triple Difference

```text
Y_utw = alpha_u + lambda_w + delta_t
      + beta * (AI_Answerability_t x PostChatGPT_w x NewUser_u) + epsilon_utw
```

The key hypothesis is that public participation falls more for new or low-reputation users in more AI-answerable tags.

## GitHub Entry Extension

```text
GithubEntry_lw = alpha_l + lambda_w
               + beta * (SO_Dependence_l x PostChatGPT_w) + epsilon_lw
```

Language or ecosystem-level Stack Overflow dependence is measured pre-treatment. GitHub outcomes focus on entry: first contributions, first pull requests, first issues, forks, comments, and activity in small repositories.

## Minimum Robustness

- Leads and lags for pre-trends.
- Placebo treatment date in 2021.
- Exclude AI and machine-learning tags.
- Exclude transition weeks around 2022-11-30.
- Compare large and small tags.
- Compare all `AI_Answerability` versions.
- Winsorize extreme outcomes.
- Cluster standard errors by tag.
- Report levels, `log(1 + y)`, and rates.
- Document all sample restrictions.

## Current First-Iteration Boundary

This repository iteration only builds the reproducible scaffold, SQL extracts, cleaning scripts, feature builders, and simulated-data tests. No real treatment effects are estimated until source data are downloaded and audited.
