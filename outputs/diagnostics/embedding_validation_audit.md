# Embedding-based external validation of AI-answerability proxy

_Generated: 2026-05-28T05:44:00_


## Sample

- N = 1000 random pre-ChatGPT questions

- 100 unique tags represented

- 100 tags matched with structural index


## Exemplar prompts


**Easy (high LLM-answerability expected):**

- How do I reverse a string in Python?

- What is the syntax for a for-loop in JavaScript?

- How do I parse JSON in Java?

- How can I sort a list of dictionaries by a key in Python?

- How do I write a basic React functional component?

- What is the difference between map and forEach in JavaScript?


**Hard (low LLM-answerability expected):**

- My company-specific build pipeline crashes with code 137 only on our internal CI runner after Kubernetes 1.27 upgrade

- Why does our custom CUDA kernel deadlock on our A100 when launched from PyTorch 2.0.1 in our private cluster

- Our legacy authentication microservice returns 503 only when called from container deployed to our Tencent Cloud production environment with cilium CNI

- Specific version conflict between our internal protobuf fork and grpc 1.58 on RHEL 8 with FIPS mode enabled

- Architecture decision: should we use saga or two-phase commit for our specific event-sourced inventory system with current Kafka topology

- Compiler error on private toolchain when cross-compiling proprietary firmware for our internal RISC-V SoC under Yocto Honister


## Correlations


| structural_var              |   pearson_r |   pearson_p |   spearman_r |   spearman_p |
|:----------------------------|------------:|------------:|-------------:|-------------:|
| ai_answerability_structural |    0.408856 | 2.40766e-05 |     0.508803 |  6.47939e-08 |
| ai_answerability_zscore     |    0.443607 | 3.7904e-06  |     0.501746 |  1.04946e-07 |
| ai_answerability_pca        |    0.477875 | 4.95992e-07 |     0.459886 |  1.48271e-06 |
| ai_answerability_quantile   |    0.504049 | 8.97693e-08 |     0.525442 |  1.98852e-08 |


## Top-5 tags by embedding score


| tag        |   embed_answerability_mean |   ai_answerability_structural |   n_questions |
|:-----------|---------------------------:|------------------------------:|--------------:|
| list       |                   0.18918  |                      1.02882  |             6 |
| dictionary |                   0.170086 |                      0.97574  |             4 |
| arrays     |                   0.156812 |                      0.967059 |            24 |
| for-loop   |                   0.143711 |                      0.730697 |             1 |
| json       |                   0.136357 |                      0.441868 |             9 |


## Bottom-5 tags by embedding score


| tag                 |   embed_answerability_mean |   ai_answerability_structural |   n_questions |
|:--------------------|---------------------------:|------------------------------:|--------------:|
| git                 |                 -0.0866223 |                    -0.116938  |             4 |
| docker              |                 -0.118515  |                    -0.518369  |             6 |
| apache-spark        |                 -0.121279  |                    -0.329303  |             2 |
| amazon-web-services |                 -0.123099  |                    -0.344883  |             8 |
| kubernetes          |                 -0.259829  |                    -0.0309327 |             2 |