-- Stack Overflow user-group-tag-week panel for top 100 pre-ChatGPT tags.
-- Preferred SEDE extract for H2 because user-level exports hit the 50,000 row limit.
-- Window: 2021-2023
-- Export as: stackoverflow_user_group_tag_week_2021_2023.csv

WITH TopTags AS (
    SELECT TOP 100
        t.TagName,
        COUNT(*) AS PreQuestions
    FROM Posts q
    INNER JOIN PostTags pt ON q.Id = pt.PostId
    INNER JOIN Tags t ON pt.TagId = t.Id
    WHERE q.PostTypeId = 1
      AND q.CreationDate >= '2018-01-01'
      AND q.CreationDate < '2022-11-30'
    GROUP BY t.TagName
    ORDER BY COUNT(*) DESC
),
TaggedQuestions AS (
    SELECT
        q.OwnerUserId AS UserId,
        DATEADD(day, -DATEDIFF(day, 0, q.CreationDate) % 7, CAST(q.CreationDate AS date)) AS WeekStart,
        t.TagName,
        1 AS IsQuestion,
        0 AS IsAnswer,
        u.Reputation,
        DATEDIFF(day, u.CreationDate, q.CreationDate) AS UserAgeDays
    FROM Posts q
    INNER JOIN PostTags pt ON q.Id = pt.PostId
    INNER JOIN Tags t ON pt.TagId = t.Id
    INNER JOIN TopTags tt ON t.TagName = tt.TagName
    LEFT JOIN Users u ON q.OwnerUserId = u.Id
    WHERE q.PostTypeId = 1
      AND q.CreationDate >= '2021-01-01'
      AND q.CreationDate < '2024-01-01'
      AND q.OwnerUserId IS NOT NULL
),
TaggedAnswers AS (
    SELECT
        a.OwnerUserId AS UserId,
        DATEADD(day, -DATEDIFF(day, 0, a.CreationDate) % 7, CAST(a.CreationDate AS date)) AS WeekStart,
        t.TagName,
        0 AS IsQuestion,
        1 AS IsAnswer,
        u.Reputation,
        DATEDIFF(day, u.CreationDate, a.CreationDate) AS UserAgeDays
    FROM Posts a
    INNER JOIN Posts q ON a.ParentId = q.Id
    INNER JOIN PostTags pt ON q.Id = pt.PostId
    INNER JOIN Tags t ON pt.TagId = t.Id
    INNER JOIN TopTags tt ON t.TagName = tt.TagName
    LEFT JOIN Users u ON a.OwnerUserId = u.Id
    WHERE a.PostTypeId = 2
      AND a.CreationDate >= '2021-01-01'
      AND a.CreationDate < '2024-01-01'
      AND a.OwnerUserId IS NOT NULL
),
Activity AS (
    SELECT UserId, WeekStart, TagName, IsQuestion, IsAnswer, Reputation, UserAgeDays FROM TaggedQuestions
    UNION ALL
    SELECT UserId, WeekStart, TagName, IsQuestion, IsAnswer, Reputation, UserAgeDays FROM TaggedAnswers
),
Grouped AS (
    SELECT
        UserId,
        WeekStart,
        TagName,
        IsQuestion,
        IsAnswer,
        CASE WHEN UserAgeDays <= 365 THEN 1 ELSE 0 END AS new_user,
        CASE WHEN Reputation <= 100 THEN 1 ELSE 0 END AS low_reputation_user
    FROM Activity
)
SELECT
    TagName AS tag,
    WeekStart AS week_start,
    new_user,
    low_reputation_user,
    COUNT(*) AS posts,
    SUM(IsQuestion) AS questions,
    SUM(IsAnswer) AS answers,
    COUNT(DISTINCT UserId) AS unique_users
FROM Grouped
GROUP BY TagName, WeekStart, new_user, low_reputation_user
ORDER BY TagName, WeekStart, new_user, low_reputation_user;
