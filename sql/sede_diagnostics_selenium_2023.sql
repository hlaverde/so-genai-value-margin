-- Diagnostic query: check whether the selenium tag disappeared or moved to related tags.
-- Run in Stack Exchange Data Explorer for Stack Overflow.

SELECT
    t.TagName AS tag,
    COUNT(*) AS questions,
    MIN(p.CreationDate) AS first_question,
    MAX(p.CreationDate) AS last_question
FROM Posts p
JOIN PostTags pt
    ON p.Id = pt.PostId
JOIN Tags t
    ON pt.TagId = t.Id
WHERE p.PostTypeId = 1
  AND p.CreationDate >= '2023-02-01'
  AND p.CreationDate < '2023-04-01'
  AND t.TagName IN (
      'selenium',
      'selenium-webdriver',
      'selenium-chromedriver',
      'webdriver',
      'chromedriver'
  )
GROUP BY t.TagName
ORDER BY t.TagName;
