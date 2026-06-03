-- Parameterized Stack Overflow tag-week panel for SEDE.
-- Uses Posts.AnswerCount instead of joining answer posts to reduce SEDE timeouts.
-- Export files as stackoverflow_tag_week_YYYY_YYYY.csv and combine without manual edits.

##StartDate:string?2018-01-01##
##EndDate:string?2019-12-31##

WITH QuestionTags AS (
    SELECT
        q.Id AS QuestionId,
        q.OwnerUserId,
        q.CreationDate,
        DATEADD(day, -DATEDIFF(day, 0, q.CreationDate) % 7, CAST(q.CreationDate AS date)) AS WeekStart,
        q.AcceptedAnswerId,
        q.Score,
        q.ClosedDate,
        q.AnswerCount,
        t.TagName
    FROM Posts q
    INNER JOIN PostTags pt ON q.Id = pt.PostId
    INNER JOIN Tags t ON pt.TagId = t.Id
    WHERE q.PostTypeId = 1
      AND q.CreationDate >= CAST(##StartDate## AS datetime)
      AND q.CreationDate < DATEADD(day, 1, CAST(##EndDate## AS datetime))
)
SELECT
    qt.TagName AS tag,
    qt.WeekStart AS week_start,
    COUNT(*) AS questions,
    SUM(COALESCE(qt.AnswerCount, 0)) AS answers,
    SUM(CASE WHEN qt.AcceptedAnswerId IS NOT NULL THEN 1 ELSE 0 END) AS accepted_answers,
    AVG(CASE WHEN qt.AnswerCount > 0 THEN 1.0 ELSE 0.0 END) AS answer_rate,
    AVG(CAST(qt.Score AS float)) AS avg_score,
    SUM(CASE WHEN qt.ClosedDate IS NOT NULL THEN 1 ELSE 0 END) AS closed_questions,
    COUNT(DISTINCT qt.OwnerUserId) AS unique_users
FROM QuestionTags qt
GROUP BY qt.TagName, qt.WeekStart
ORDER BY qt.TagName, qt.WeekStart;
