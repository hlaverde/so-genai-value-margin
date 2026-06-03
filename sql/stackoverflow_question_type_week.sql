-- Tag-week-type panel for mechanism tests.
-- Run in Stack Exchange Data Explorer against Stack Overflow.
-- Save as: data/raw/stackoverflow/stackoverflow_question_type_week.csv
--
-- This builds coarse question-type categories from title/body structure.
-- The categories are intentionally simple and reproducible. They are not a
-- substitute for the external AI-answerability validation sample.

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
QuestionTyped AS (
    SELECT
        p.Id AS question_id,
        DATEADD(week, DATEDIFF(week, 0, p.CreationDate), 0) AS week_start,
        t.TagName AS tag,
        CASE
            WHEN LOWER(p.Title) LIKE 'how %'
              OR LOWER(p.Title) LIKE 'how do %'
              OR LOWER(p.Title) LIKE 'how to %'
            THEN 'how_to'
            WHEN (LOWER(p.Title) LIKE '% error %'
              OR LOWER(p.Title) LIKE '% exception %'
              OR LOWER(p.Title) LIKE '% traceback %'
              OR LOWER(p.Title) LIKE '% not working %')
              AND LEN(p.Body) < 1600
            THEN 'debugging_simple'
            WHEN p.Body LIKE '%<code>%' AND LEN(p.Body) < 1200
            THEN 'short_code'
            WHEN p.Body LIKE '%<code>%' AND LEN(p.Body) >= 3000
            THEN 'long_code'
            WHEN LOWER(p.Title) LIKE '% version %'
              OR LOWER(p.Body) LIKE '% version %'
              OR LOWER(p.Body) LIKE '% environment %'
              OR LOWER(p.Body) LIKE '% operating system %'
            THEN 'version_environment_specific'
            WHEN LOWER(p.Title) LIKE '% architecture %'
              OR LOWER(p.Title) LIKE '% design %'
              OR LOWER(p.Title) LIKE '% best practice %'
            THEN 'advanced_architecture'
            ELSE 'other_conceptual'
        END AS question_type,
        CASE
            WHEN LOWER(p.Title) LIKE 'how %'
              OR LOWER(p.Title) LIKE 'how do %'
              OR LOWER(p.Title) LIKE 'how to %'
              OR ((LOWER(p.Title) LIKE '% error %'
                OR LOWER(p.Title) LIKE '% exception %'
                OR LOWER(p.Title) LIKE '% traceback %'
                OR LOWER(p.Title) LIKE '% not working %') AND LEN(p.Body) < 1600)
              OR (p.Body LIKE '%<code>%' AND LEN(p.Body) < 1200)
            THEN 1 ELSE 0
        END AS substitutable_type,
        p.OwnerUserId,
        p.Score,
        p.AnswerCount,
        p.AcceptedAnswerId,
        p.ClosedDate
    FROM Posts p
    INNER JOIN PostTags pt ON p.Id = pt.PostId
    INNER JOIN Tags t ON pt.TagId = t.Id
    INNER JOIN TopTags tt ON t.TagName = tt.TagName
    WHERE p.PostTypeId = 1
      AND p.CreationDate >= '2018-01-01'
)
SELECT
    tag,
    week_start,
    question_type,
    substitutable_type,
    COUNT(*) AS questions,
    SUM(CAST(AnswerCount AS int)) AS answers,
    SUM(CASE WHEN AcceptedAnswerId IS NOT NULL THEN 1 ELSE 0 END) AS accepted_answers,
    AVG(CAST(Score AS float)) AS avg_score,
    SUM(CASE WHEN ClosedDate IS NOT NULL THEN 1 ELSE 0 END) AS closed_questions,
    COUNT(DISTINCT OwnerUserId) AS unique_users
FROM QuestionTyped
GROUP BY tag, week_start, question_type, substitutable_type
ORDER BY tag, week_start, question_type;
