-- Stack Overflow user-tag-week panel for Stack Exchange Data Explorer.
-- Export as: stackoverflow_user_tag_week.csv

WITH TaggedQuestions AS (
    SELECT
        q.Id AS QuestionId,
        q.OwnerUserId AS UserId,
        DATEADD(day, -DATEDIFF(day, 0, q.CreationDate) % 7, CAST(q.CreationDate AS date)) AS WeekStart,
        t.TagName,
        1 AS IsQuestion,
        0 AS IsAnswer
    FROM Posts q
    INNER JOIN PostTags pt ON q.Id = pt.PostId
    INNER JOIN Tags t ON pt.TagId = t.Id
    WHERE q.PostTypeId = 1
      AND q.CreationDate >= '2018-01-01'
      AND q.OwnerUserId IS NOT NULL
),
TaggedAnswers AS (
    SELECT
        a.Id AS AnswerId,
        a.OwnerUserId AS UserId,
        DATEADD(day, -DATEDIFF(day, 0, a.CreationDate) % 7, CAST(a.CreationDate AS date)) AS WeekStart,
        t.TagName,
        0 AS IsQuestion,
        1 AS IsAnswer
    FROM Posts a
    INNER JOIN Posts q ON a.ParentId = q.Id
    INNER JOIN PostTags pt ON q.Id = pt.PostId
    INNER JOIN Tags t ON pt.TagId = t.Id
    WHERE a.PostTypeId = 2
      AND a.CreationDate >= '2018-01-01'
      AND a.OwnerUserId IS NOT NULL
),
Activity AS (
    SELECT UserId, WeekStart, TagName, IsQuestion, IsAnswer FROM TaggedQuestions
    UNION ALL
    SELECT UserId, WeekStart, TagName, IsQuestion, IsAnswer FROM TaggedAnswers
)
SELECT
    a.UserId AS user_id,
    a.TagName AS tag,
    a.WeekStart AS week_start,
    MIN(u.Reputation) AS reputation_initial,
    DATEDIFF(day, MIN(u.CreationDate), a.WeekStart) AS user_age_days,
    COUNT(*) AS posts,
    SUM(a.IsQuestion) AS questions,
    SUM(a.IsAnswer) AS answers
FROM Activity a
LEFT JOIN Users u ON a.UserId = u.Id
GROUP BY a.UserId, a.TagName, a.WeekStart
ORDER BY a.UserId, a.TagName, a.WeekStart;
