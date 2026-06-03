# Reusable Artifact Funnel — Bloque 0 Diagnostic Report

_Generated: 2026-05-26T11:52:20_  
_Project root: `D:\DocumentosHL\Documentos\Documents\2021\Henry Laverde\2026\Investigación\Paper de IA\Propuesta No. 1\ai-knowledge-commons-shock`_

> Bloque 0 verifica disponibilidad y esquema antes de construir el funnel. 
> No procesa los 8M de filas; solo muestras (nrows=5000) por archivo.


## 1. Raw Stack Overflow files inventory

- Folder: `D:\DocumentosHL\Documentos\Documents\2021\Henry Laverde\2026\Investigación\Paper de IA\Propuesta No. 1\ai-knowledge-commons-shock\data\raw\stackoverflow`
- Total `stackoverflow_question_type_raw_*.csv` files: **476**
- Sample inspected (first / middle / last):
  - `stackoverflow_question_type_raw_2020-02-01_2020-02-05.csv` (4045.9 KB)
  - `stackoverflow_question_type_raw_2022-07-09_2022-07-13.csv` (2979.2 KB)
  - `stackoverflow_question_type_raw_2024-12-29_2025-01-01.csv` (225.4 KB)

## 2. Raw schema verification

### `stackoverflow_question_type_raw_2020-02-01_2020-02-05.csv` (first 5000 rows)

- Required columns missing: **NONE**
- Extra columns beyond spec: NONE

#### dtypes

```
<class 'pandas.DataFrame'>
RangeIndex: 5000 entries, 0 to 4999
Data columns (total 12 columns):
 #   Column               Non-Null Count  Dtype  
---  ------               --------------  -----  
 0   tag                  5000 non-null   str    
 1   week_start           5000 non-null   str    
 2   question_id          5000 non-null   int64  
 3   owner_user_id        4775 non-null   float64
 4   creation_date        5000 non-null   str    
 5   title                5000 non-null   str    
 6   body_length          5000 non-null   int64  
 7   has_code             5000 non-null   int64  
 8   score                5000 non-null   int64  
 9   answer_count         5000 non-null   int64  
 10  has_accepted_answer  5000 non-null   int64  
 11  is_closed            5000 non-null   int64  
dtypes: float64(1), int64(7), str(4)
memory usage: 980.3 KB
```

#### head(3)

| tag          | week_start          |   question_id |    owner_user_id | creation_date       | title                                                                |   body_length |   has_code |   score |   answer_count |   has_accepted_answer |   is_closed |
|:-------------|:--------------------|--------------:|-----------------:|:--------------------|:---------------------------------------------------------------------|--------------:|-----------:|--------:|---------------:|----------------------:|------------:|
| wordpress    | 2020-01-27 00:00:00 |      60012798 |      1.27145e+07 | 2020-02-01 00:00:24 | How can I link my JavaScript file properly with enqueue in WordPress |          1841 |          1 |       0 |              1 |                     0 |           0 |
| apache-spark | 2020-01-27 00:00:00 |      60012805 | 892857           | 2020-02-01 00:01:35 | Implicit class not working for Generic Type                          |          2029 |          1 |      -1 |              1 |                     0 |           0 |
| scala        | 2020-01-27 00:00:00 |      60012805 | 892857           | 2020-02-01 00:01:35 | Implicit class not working for Generic Type                          |          2029 |          1 |      -1 |              1 |                     0 |           0 |

#### missing per column (only nonzero)

|               |   missing |   pct |
|:--------------|----------:|------:|
| owner_user_id |       225 |   4.5 |

#### quick checks

- `is_closed` unique: [0, 1]
- `has_accepted_answer` unique: [0, 1]
- `has_code` unique: [0, 1]
- `score` range: [-5, 303], mean=1.10, n_negative=445, n_zero=2398
- `answer_count` range: [0, 23], pct(>0)=83.96%
- duplicates by (question_id, tag) in this sample: **0**
- `week_start` range in sample: 2020-01-27 → 2020-02-03
- tags in sample: n=100, top5={'python': 531, 'javascript': 354, 'java': 253, 'c#': 164, 'html': 158}

### `stackoverflow_question_type_raw_2022-07-09_2022-07-13.csv` (first 5000 rows)

- Required columns missing: **NONE**
- Extra columns beyond spec: NONE

#### dtypes

```
<class 'pandas.DataFrame'>
RangeIndex: 5000 entries, 0 to 4999
Data columns (total 12 columns):
 #   Column               Non-Null Count  Dtype  
---  ------               --------------  -----  
 0   tag                  5000 non-null   str    
 1   week_start           5000 non-null   str    
 2   question_id          5000 non-null   int64  
 3   owner_user_id        4878 non-null   float64
 4   creation_date        5000 non-null   str    
 5   title                5000 non-null   str    
 6   body_length          5000 non-null   int64  
 7   has_code             5000 non-null   int64  
 8   score                5000 non-null   int64  
 9   answer_count         5000 non-null   int64  
 10  has_accepted_answer  5000 non-null   int64  
 11  is_closed            5000 non-null   int64  
dtypes: float64(1), int64(7), str(4)
memory usage: 989.4 KB
```

#### head(3)

| tag                   | week_start          |   question_id |   owner_user_id | creation_date       | title                                                                                             |   body_length |   has_code |   score |   answer_count |   has_accepted_answer |   is_closed |
|:----------------------|:--------------------|--------------:|----------------:|:--------------------|:--------------------------------------------------------------------------------------------------|--------------:|-----------:|--------:|---------------:|----------------------:|------------:|
| javascript            | 2022-07-04 00:00:00 |      72918009 |     1.92552e+07 | 2022-07-09 00:00:38 | Any way to quickly find out from what Javascript file and code line a custom event is dispatched? |           569 |          1 |       0 |              1 |                     1 |           0 |
| go                    | 2022-07-04 00:00:00 |      72918012 |     1.95137e+07 | 2022-07-09 00:01:51 | How to pass cloud-init file to vm in gcloud using golang?                                         |           970 |          1 |       1 |              0 |                     0 |           0 |
| google-cloud-platform | 2022-07-04 00:00:00 |      72918012 |     1.95137e+07 | 2022-07-09 00:01:51 | How to pass cloud-init file to vm in gcloud using golang?                                         |           970 |          1 |       1 |              0 |                     0 |           0 |

#### missing per column (only nonzero)

|               |   missing |   pct |
|:--------------|----------:|------:|
| owner_user_id |       122 |  2.44 |

#### quick checks

- `is_closed` unique: [0, 1]
- `has_accepted_answer` unique: [0, 1]
- `has_code` unique: [0, 1]
- `score` range: [-6, 154], mean=0.53, n_negative=552, n_zero=2638
- `answer_count` range: [0, 22], pct(>0)=80.94%
- duplicates by (question_id, tag) in this sample: **0**
- `week_start` range in sample: 2022-07-04 → 2022-07-11
- tags in sample: n=100, top5={'python': 641, 'javascript': 443, 'reactjs': 243, 'html': 172, 'c#': 163}

### `stackoverflow_question_type_raw_2024-12-29_2025-01-01.csv` (first 5000 rows)

- Required columns missing: **NONE**
- Extra columns beyond spec: NONE

#### dtypes

```
<class 'pandas.DataFrame'>
RangeIndex: 1518 entries, 0 to 1517
Data columns (total 12 columns):
 #   Column               Non-Null Count  Dtype  
---  ------               --------------  -----  
 0   tag                  1518 non-null   str    
 1   week_start           1518 non-null   str    
 2   question_id          1518 non-null   int64  
 3   owner_user_id        1513 non-null   float64
 4   creation_date        1518 non-null   str    
 5   title                1518 non-null   str    
 6   body_length          1518 non-null   int64  
 7   has_code             1518 non-null   int64  
 8   score                1518 non-null   int64  
 9   answer_count         1518 non-null   int64  
 10  has_accepted_answer  1518 non-null   int64  
 11  is_closed            1518 non-null   int64  
dtypes: float64(1), int64(7), str(4)
memory usage: 312.0 KB
```

#### head(3)

| tag                 | week_start          |   question_id |   owner_user_id | creation_date       | title                                                                                             |   body_length |   has_code |   score |   answer_count |   has_accepted_answer |   is_closed |
|:--------------------|:--------------------|--------------:|----------------:|:--------------------|:--------------------------------------------------------------------------------------------------|--------------:|-----------:|--------:|---------------:|----------------------:|------------:|
| apache-spark        | 2024-12-23 00:00:00 |      79314770 |     2.89516e+07 | 2024-12-29 00:19:22 | spark-shell and pyspark command is not getting initialized after the pre-requisites has been done |          6360 |          1 |       0 |              1 |                     0 |           0 |
| r                   | 2024-12-23 00:00:00 |      79314775 |     6.67949e+06 | 2024-12-29 00:27:08 | Access an R shiny app running on a port from another port via httpuv                              |          2620 |          1 |       3 |              1 |                     1 |           0 |
| amazon-web-services | 2024-12-23 00:00:00 |      79314785 |     1.39517e+07 | 2024-12-29 00:37:27 | pyppeteer: Browser closed unexpectedly on Python 3.9 AWS Lambda Function                          |          4333 |          1 |       1 |              1 |                     0 |           0 |

#### missing per column (only nonzero)

|               |   missing |   pct |
|:--------------|----------:|------:|
| owner_user_id |         5 |  0.33 |

#### quick checks

- `is_closed` unique: [0, 1]
- `has_accepted_answer` unique: [0, 1]
- `has_code` unique: [0, 1]
- `score` range: [-7, 15], mean=0.65, n_negative=106, n_zero=734
- `answer_count` range: [0, 8], pct(>0)=72.92%
- duplicates by (question_id, tag) in this sample: **0**
- `week_start` range in sample: 2024-12-23 → 2024-12-30
- tags in sample: n=97, top5={'python': 157, 'javascript': 84, 'java': 60, 'android': 58, 'c#': 57}

### Raw schema summary

- ✅ All 3 inspected raw files contain the 12 required columns.


## 3. Master panel — `stackoverflow_question_type_master_panel.csv`

- Path: `D:\DocumentosHL\Documentos\Documents\2021\Henry Laverde\2026\Investigación\Paper de IA\Propuesta No. 1\ai-knowledge-commons-shock\data\processed\stackoverflow_question_type_master_panel.csv`
- Rows: **164,351** | Cols: **34**
- Unique tags: **100**
- Unique question_type values: **7**

#### question_type value counts (panel cells)

| question_type                |   count |
|:-----------------------------|--------:|
| long_code                    |   26073 |
| how_to                       |   25990 |
| short_code                   |   25911 |
| debugging_simple             |   25458 |
| other_conceptual             |   25044 |
| version_environment_specific |   22866 |
| advanced_architecture        |   13009 |


#### substitutable_type counts

|   substitutable_type |   count |
|---------------------:|--------:|
|                    1 |  128476 |
|                    0 |   35875 |

- week_start range: **2020-01-06 → 2024-12-30**
- distinct weeks: **261**
- week-to-week gap (days): min=7, max=7, modal=7, mean=7.00
- non-7-day gaps: **0** (0 = perfectly weekly)

#### dtypes

```
<class 'pandas.DataFrame'>
RangeIndex: 164351 entries, 0 to 164350
Data columns (total 34 columns):
 #   Column                       Non-Null Count   Dtype  
---  ------                       --------------   -----  
 0   tag                          164351 non-null  str    
 1   week_start                   164351 non-null  str    
 2   question_type                164351 non-null  str    
 3   substitutable_type           164351 non-null  int64  
 4   questions                    164351 non-null  int64  
 5   answers                      164351 non-null  int64  
 6   accepted_answers             164351 non-null  int64  
 7   avg_score                    164351 non-null  float64
 8   closed_questions             164351 non-null  int64  
 9   unique_users                 164351 non-null  int64  
 10  body_length_mean             164351 non-null  float64
 11  code_questions               164351 non-null  int64  
 12  answer_rate                  164351 non-null  float64
 13  accepted_share               164351 non-null  float64
 14  closed_share                 164351 non-null  float64
 15  code_share                   164351 non-null  float64
 16  year                         164351 non-null  int64  
 17  ai_answerability_zscore      164351 non-null  float64
 18  ai_answerability_pca         164351 non-null  float64
 19  ai_answerability_quantile    164351 non-null  float64
 20  ai_answerability_structural  164351 non-null  float64
 21  questions_pre                164351 non-null  int64  
 22  accepted_answer_rate_pre     164351 non-null  float64
 23  short_code_share_pre         164351 non-null  float64
 24  how_to_share_pre             164351 non-null  float64
 25  post_chatgpt                 164351 non-null  int64  
 26  post_chatgpt_bool            164351 non-null  bool   
 27  log_questions_p1             164351 non-null  float64
 28  log_questions                164351 non-null  float64
 29  log_unique_users_p1          164351 non-null  float64
 30  accepted_per_q               164351 non-null  float64
 31  weeks_from_start             164351 non-null  int64  
 32  weeks_from_chatgpt           164351 non-null  int64  
 33  tag_qtype                    164351 non-null  str    
dtypes: bool(1), float64(17), int64(12), str(4)
memory usage: 50.3 MB
```

#### head(3)

| tag   | week_start   | question_type         |   substitutable_type |   questions |   answers |   accepted_answers |   avg_score |   closed_questions |   unique_users |   body_length_mean |   code_questions |   answer_rate |   accepted_share |   closed_share |   code_share |   year |   ai_answerability_zscore |   ai_answerability_pca |   ai_answerability_quantile |   ai_answerability_structural |   questions_pre |   accepted_answer_rate_pre |   short_code_share_pre |   how_to_share_pre |   post_chatgpt | post_chatgpt_bool   |   log_questions_p1 |   log_questions |   log_unique_users_p1 |   accepted_per_q |   weeks_from_start |   weeks_from_chatgpt | tag_qtype                   |
|:------|:-------------|:----------------------|---------------------:|------------:|----------:|-------------------:|------------:|-------------------:|---------------:|-------------------:|-----------------:|--------------:|-----------------:|---------------:|-------------:|-------:|--------------------------:|-----------------------:|----------------------------:|------------------------------:|----------------:|---------------------------:|-----------------------:|-------------------:|---------------:|:--------------------|-------------------:|----------------:|----------------------:|-----------------:|-------------------:|---------------------:|:----------------------------|
| .net  | 2020-01-06   | advanced_architecture |                    0 |           3 |         3 |                  1 |    2.33333  |                  0 |              3 |            1512.33 |                2 |       1       |        0.333333  |      0         |     0.666667 |   2020 |                 -0.570197 |               -1.05936 |                           0 |                     -0.484784 |           65488 |                   0.425253 |               0.144413 |           0.250686 |              0 | False               |            1.38629 |         1.09861 |               1.38629 |        0.333333  |                  0 |                 -152 | .net::advanced_architecture |
| .net  | 2020-01-06   | debugging_simple      |                    1 |          22 |        24 |                  2 |    0.727273 |                  1 |             20 |            3478.5  |               20 |       1.09091 |        0.0909091 |      0.0454545 |     0.909091 |   2020 |                 -0.570197 |               -1.05936 |                           0 |                     -0.484784 |           65488 |                   0.425253 |               0.144413 |           0.250686 |              0 | False               |            3.13549 |         3.09104 |               3.04452 |        0.0909091 |                  0 |                 -152 | .net::debugging_simple      |
| .net  | 2020-01-06   | how_to                |                    1 |          56 |        64 |                 28 |    1.05357  |                  5 |             47 |            1491.86 |               45 |       1.14286 |        0.5       |      0.0892857 |     0.803571 |   2020 |                 -0.570197 |               -1.05936 |                           0 |                     -0.484784 |           65488 |                   0.425253 |               0.144413 |           0.250686 |              0 | False               |            4.04305 |         4.02535 |               3.8712  |        0.5       |                  0 |                 -152 | .net::how_to                |

#### columns with any missing (nonzero only)

NONE — fully populated


## 4. AI answerability — `ai_answerability_real.csv`

- Path: `D:\DocumentosHL\Documentos\Documents\2021\Henry Laverde\2026\Investigación\Paper de IA\Propuesta No. 1\ai-knowledge-commons-shock\data\processed\ai_answerability_real.csv`
- Rows: **100** | Cols: **13**
- Unique tags: **100**

#### dtypes

```
<class 'pandas.DataFrame'>
RangeIndex: 100 entries, 0 to 99
Data columns (total 13 columns):
 #   Column                       Non-Null Count  Dtype  
---  ------                       --------------  -----  
 0   tag                          100 non-null    str    
 1   questions_pre                100 non-null    int64  
 2   accepted_answers_pre         100 non-null    int64  
 3   answer_rate_pre              100 non-null    float64
 4   historical_frequency_pre     100 non-null    int64  
 5   tag_maturity_weeks_pre       100 non-null    int64  
 6   accepted_answer_rate_pre     100 non-null    float64
 7   short_code_share_pre         100 non-null    float64
 8   how_to_share_pre             100 non-null    float64
 9   ai_answerability_zscore      100 non-null    float64
 10  ai_answerability_pca         100 non-null    float64
 11  ai_answerability_quantile    100 non-null    float64
 12  ai_answerability_structural  100 non-null    float64
dtypes: float64(8), int64(4), str(1)
memory usage: 11.0 KB
```

#### head(5)

| tag                 |   questions_pre |   accepted_answers_pre |   answer_rate_pre |   historical_frequency_pre |   tag_maturity_weeks_pre |   accepted_answer_rate_pre |   short_code_share_pre |   how_to_share_pre |   ai_answerability_zscore |   ai_answerability_pca |   ai_answerability_quantile |   ai_answerability_structural |
|:--------------------|----------------:|-----------------------:|------------------:|---------------------------:|-------------------------:|---------------------------:|-----------------------:|-------------------:|--------------------------:|-----------------------:|----------------------------:|------------------------------:|
| .net                |           65488 |                  27849 |          0.767664 |                      65488 |                      257 |                   0.425253 |              0.144413  |           0.250686 |                 -0.570197 |              -1.05936  |                        0    |                     -0.484784 |
| .net-core           |           34564 |                  15576 |          0.790963 |                      34564 |                      257 |                   0.450642 |              0.117961  |           0.242967 |                 -0.559505 |              -0.702178 |                        0    |                     -0.308164 |
| ajax                |           44257 |                  17454 |          0.754176 |                      44257 |                      257 |                   0.394378 |              0.0669273 |           0.27978  |                 -0.773679 |              -2.29295  |                        0    |                     -0.708206 |
| algorithm           |           36579 |                  18340 |          0.861556 |                      36579 |                      257 |                   0.501381 |              0.146283  |           0.183148 |                 -0.398763 |               1.22026  |                        0.25 |                      0.272705 |
| amazon-web-services |           91250 |                  35753 |          0.809569 |                      91250 |                      257 |                   0.391814 |              0.123451  |           0.270783 |                 -0.430425 |              -1.09855  |                        0    |                     -0.344883 |

#### columns with any missing

NONE — fully populated


## 5. Cross-checks panel ↔ answerability

- Tags in master panel: **100**
- Tags in answerability: **100**
- Intersection: **100**
- In master but NOT in answerability: NONE
- In answerability but NOT in master: NONE

## 6. Post-ChatGPT cutoff sanity (2022-11-30)

- Panel cells with week_start < 2022-11-30: **99,185**
- Panel cells with week_start ≥ 2022-11-30: **65,166**
- Existing `post_chatgpt_bool` column sum: **65,166**
  - ✅ Matches threshold-based count.

## 7. Conclusions

- Required raw columns for the Reusable Artifact Funnel **are present** (see §2).
- `is_closed` and `has_accepted_answer` are 0/1 → can be used directly without reconstruction.
- Master panel covers 2020–2024 with 100 tags × 7 question_types (see §3).
- AI answerability is at tag level and matches master panel tag set (see §5).
- ✅ Ready to proceed to **Bloque 1** (build funnel panel) once user approves.