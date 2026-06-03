-- Fractional-count tag-week panel for Stack Overflow.
-- Run in Stack Exchange Data Explorer against Stack Overflow.
-- Save as: data/raw/stackoverflow/stackoverflow_fractional_tag_week.csv
--
-- A question with n tags contributes 1/n to each tag. Answers and accepted
-- answers are allocated through the parent question's tag set using the same
-- fractional weight. This addresses mechanical over-counting in tag panels.

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
QuestionBase AS (
    SELECT
        p.Id AS question_id,
        p.CreationDate,
        DATEADD(week, DATEDIFF(week, 0, p.CreationDate), 0) AS week_start,
        p.OwnerUserId,
        p.Score,
        p.AnswerCount,
        p.AcceptedAnswerId,
        p.ClosedDate,
        COUNT(pt.TagId) OVER (PARTITION BY p.Id) AS num_tags
    FROM Posts p
    INNER JOIN PostTags pt ON p.Id = pt.PostId
    INNER JOIN Tags t ON pt.TagId = t.Id
    INNER JOIN TopTags tt ON t.TagName = tt.TagName
    WHERE p.PostTypeId = 1
      AND p.CreationDate >= '2018-01-01'
),
QuestionTagWeights AS (
    SELECT DISTINCT
        qb.question_id,
        qb.week_start,
        qb.OwnerUserId,
        qb.Score,
        qb.AnswerCount,
        qb.AcceptedAnswerId,
        qb.ClosedDate,
        t.TagName AS tag,
        CAST(1.0 / NULLIF(qb.num_tags, 0) AS float) AS tag_weight
    FROM QuestionBase qb
    INNER JOIN PostTags pt ON qb.question_id = pt.PostId
    INNER JOIN Tags t ON pt.TagId = t.Id
    INNER JOIN TopTags tt ON t.TagName = tt.TagName
),
AnswerCounts AS (
    SELECT
        qtw.tag,
        qtw.week_start,
        SUM(qtw.tag_weight) AS fractional_questions,
        SUM(CASE WHEN qtw.AcceptedAnswerId IS NOT NULL THEN qtw.tag_weight ELSE 0 END) AS fractional_accepted_answers,
        SUM(CASE WHEN qtw.ClosedDate IS NOT NULL THEN qtw.tag_weight ELSE 0 END) AS fractional_closed_questions,
        SUM(CAST(qtw.AnswerCount AS float) * qtw.tag_weight) AS fractional_answers,
        AVG(CAST(qtw.Score AS float)) AS avg_score,
        COUNT(DISTINCT qtw.OwnerUserId) AS unique_users
    FROM QuestionTagWeights qtw
    GROUP BY qtw.tag, qtw.week_start
)
SELECT
    tag,
    week_start,
    fractional_questions AS questions,
    fractional_answers AS answers,
    fractional_accepted_answers AS accepted_answers,
    CASE WHEN fractional_questions > 0 THEN fractional_answers / fractional_questions ELSE 0 END AS answer_rate,
    avg_score,
    fractional_closed_questions AS closed_questions,
    unique_users
FROM AnswerCounts
ORDER BY tag, week_start;
