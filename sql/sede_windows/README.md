# Parameterized SEDE Window Queries

Use these if the full Stack Overflow SQL files time out.

In Stack Exchange Data Explorer, parameters can be declared using comments like:

```sql
##StartDate:string?2018-01-01##
##EndDate:string?2018-12-31##
```

Run one window at a time and export the resulting CSV. Keep definitions unchanged across windows.

Recommended first windows:

- 2018-01-01 to 2019-12-31
- 2020-01-01 to 2021-12-31
- 2022-01-01 to 2023-12-31
- 2024-01-01 to latest available date

If a two-year window is too large, split into single years.
