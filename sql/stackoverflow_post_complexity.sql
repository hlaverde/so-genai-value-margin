-- Stack Overflow post-level complexity extract for Stack Exchange Data Explorer.
-- Export as: stackoverflow_post_complexity.csv

SELECT
    q.Id AS post_id,
    q.CreationDate AS creation_date,
    t.TagName AS tag,
    LEN(q.Body) AS body_length,
    CASE WHEN q.Body LIKE '%<code>%' THEN 1 ELSE 0 END AS has_code,
    (
        SELECT COUNT(*)
        FROM PostTags pt2
        WHERE pt2.PostId = q.Id
    ) AS num_tags,
    q.AnswerCount AS answer_count,
    CASE WHEN q.AcceptedAnswerId IS NOT NULL THEN 1 ELSE 0 END AS has_accepted_answer,
    q.Score AS score,
    q.Title AS title,
    q.Body AS body
FROM Posts q
INNER JOIN PostTags pt ON q.Id = pt.PostId
INNER JOIN Tags t ON pt.TagId = t.Id
WHERE q.PostTypeId = 1
  AND q.CreationDate >= '2018-01-01'
ORDER BY q.CreationDate, q.Id, t.TagName;
