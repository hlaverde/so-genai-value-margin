-- User-post entry extract for new-user and retention analysis.
-- Run in Stack Exchange Data Explorer against Stack Overflow.
-- Save year-window exports as:
--   data/raw/stackoverflow/stackoverflow_user_post_entry_2021.csv
--   data/raw/stackoverflow/stackoverflow_user_post_entry_2022.csv
--   data/raw/stackoverflow/stackoverflow_user_post_entry_2023.csv
--
-- Edit @StartDate and @EndDate for each window to avoid SEDE timeouts.

DECLARE @StartDate datetime = '2021-01-01';
DECLARE @EndDate   datetime = '2022-01-01';

WITH TopTags AS (
    SELECT TOP 100
        t.TagName,
        COUNT(*) AS QuestionsPre
    FROM Posts p
    INNER JOIN PostTags pt ON p.Id = pt.PostId
    INNER JOIN Tags t ON pt.TagId = t.Id
    WHERE p.PostTypeId = 1
      AND p.CreationDate >= '2018-01-01'
      AND p.CreationDate < '2022-11-30'
    GROUP BY t.TagName
    ORDER BY COUNT(*) DESC
),
UserFirsts AS (
    SELECT
        OwnerUserId,
        MIN(CreationDate) AS first_post_date,
        MIN(CASE WHEN PostTypeId = 1 THEN CreationDate END) AS first_question_date,
        MIN(CASE WHEN PostTypeId = 2 THEN CreationDate END) AS first_answer_date
    FROM Posts
    WHERE OwnerUserId IS NOT NULL
      AND CreationDate < @EndDate
      AND PostTypeId IN (1, 2)
    GROUP BY OwnerUserId
),
TaggedQuestions AS (
    SELECT
        p.Id AS question_id,
        t.TagName AS tag
    FROM Posts p
    INNER JOIN PostTags pt ON p.Id = pt.PostId
    INNER JOIN Tags t ON pt.TagId = t.Id
    INNER JOIN TopTags tt ON t.TagName = tt.TagName
    WHERE p.PostTypeId = 1
),
PostsWithQuestion AS (
    SELECT
        p.Id AS post_id,
        p.PostTypeId,
        CASE WHEN p.PostTypeId = 1 THEN p.Id ELSE p.ParentId END AS question_id,
        p.OwnerUserId,
        p.CreationDate,
        DATEADD(week, DATEDIFF(week, 0, p.CreationDate), 0) AS week_start,
        p.Score,
        p.AcceptedAnswerId,
        p.ParentId
    FROM Posts p
    WHERE p.PostTypeId IN (1, 2)
      AND p.OwnerUserId IS NOT NULL
      AND p.CreationDate >= @StartDate
      AND p.CreationDate < @EndDate
)
SELECT
    pwq.post_id,
    pwq.PostTypeId AS post_type_id,
    pwq.question_id,
    tq.tag,
    pwq.OwnerUserId AS user_id,
    u.Reputation AS current_reputation,
    uf.first_post_date,
    uf.first_question_date,
    uf.first_answer_date,
    CASE WHEN pwq.CreationDate = uf.first_post_date THEN 1 ELSE 0 END AS is_first_post,
    CASE WHEN pwq.PostTypeId = 1 AND pwq.CreationDate = uf.first_question_date THEN 1 ELSE 0 END AS is_first_question,
    CASE WHEN pwq.PostTypeId = 2 AND pwq.CreationDate = uf.first_answer_date THEN 1 ELSE 0 END AS is_first_answer,
    CASE WHEN u.Reputation < 100 THEN 1 ELSE 0 END AS low_reputation_current,
    pwq.CreationDate AS post_creation_date,
    pwq.week_start,
    pwq.Score AS post_score
FROM PostsWithQuestion pwq
INNER JOIN TaggedQuestions tq ON pwq.question_id = tq.question_id
INNER JOIN Users u ON pwq.OwnerUserId = u.Id
INNER JOIN UserFirsts uf ON pwq.OwnerUserId = uf.OwnerUserId
ORDER BY pwq.CreationDate, pwq.post_id, tq.tag;
