# 2025 Panel Integrity Audit Report

## Executive Conclusion

DATA PASS WITH WARNINGS: 2025 panel is usable, but the following issues require review.

## Files Audited

- Raw 2025 API folder: `D:\DocumentosHL\Documentos\Documents\2021\Henry Laverde\2026\Investigación\Paper de IA\Propuesta No. 1\ai-knowledge-commons-shock\data\raw\stackoverflow\api_2025_full_100tags`
- Raw manifest requested path: `D:\DocumentosHL\Documentos\Documents\2021\Henry Laverde\2026\Investigación\Paper de IA\Propuesta No. 1\ai-knowledge-commons-shock\data\raw\stackoverflow\api_2025_full_100tags\_manifest_2025_full_100tags.csv`
- Raw manifest actual path: `D:\DocumentosHL\Documentos\Documents\2021\Henry Laverde\2026\Investigación\Paper de IA\Propuesta No. 1\ai-knowledge-commons-shock\data\raw\stackoverflow\api_2025_full_100tags\manifest_2025_full_100tags.csv`
- Clean 2025 question-tag dataset: `D:\DocumentosHL\Documentos\Documents\2021\Henry Laverde\2026\Investigación\Paper de IA\Propuesta No. 1\ai-knowledge-commons-shock\data\processed\stackoverflow_2025_clean_question_tag.csv`
- Full 2020-2025 panel: `D:\DocumentosHL\Documentos\Documents\2021\Henry Laverde\2026\Investigación\Paper de IA\Propuesta No. 1\ai-knowledge-commons-shock\data\processed\panel_tag_week_question_type_2020_2025.csv`
- Previous 2020-2024 panel: `D:\DocumentosHL\Documentos\Documents\2021\Henry Laverde\2026\Investigación\Paper de IA\Propuesta No. 1\ai-knowledge-commons-shock\data\processed\stackoverflow_question_type_master_panel.csv`
- Fixed 100-tag source: `D:\DocumentosHL\Documentos\Documents\2021\Henry Laverde\2026\Investigación\Paper de IA\Propuesta No. 1\ai-knowledge-commons-shock\data\processed\ai_answerability_real.csv`

## Fixed 100-Tag Verification

- Fixed tags: 100
- Tag audit non-ok rows: 0

## Raw API Integrity Summary

- Total JSON files: 1465
- Invalid JSON files: 0
- Empty JSON files: 0
- Tags with raw status not ok: 0
- Page-cap flags: 0
- Failed windows: 0

## Clean 2025 Dataset Summary

- Row count: 132511
- Unique questions: 87027
- Duplicate question-tag rows: 0
- Date range: 2025-01-01 00:21:22 to 2025-12-31 23:14:43

## Panel 2020-2025 Summary

- n_rows: 186188
- n_tags: 100
- n_question_types: 7
- min_week: 2020-01-06 00:00:00
- max_week: 2025-12-29 00:00:00
- n_2025_rows: 21673
- n_2025_weeks: 52

## 2020-2024 Consistency Result

- Result: match except for documented crossing-week treatment.
- Weeks before 2024-12-30 match exactly.
- The week starting 2024-12-30 differs because the 2020-2025 panel consolidates early-2025 rows into the same Monday-start week.

## 2025 Coverage Result

- All 100 tags present in clean and panel: True
- Q4 2025 observations present: True
- The panel is observed-cell based, not a fully balanced tag x week x question_type grid.

## Clean-to-Panel Aggregation Result

- Status: ok
- Tag-week-question-type discrepancies from 2025-01-06: 0
- Note: The 2024-12-30 crossing week is excluded because the panel consolidates late-2024 and early-2025 rows.

## Question-Type Distribution Result

- Missing question-type rows: 0
- All seven taxonomy categories appear in 2024 and 2025.

## Suspicious Tags/Windows

- Tags flagged for human inspection: none
- Suspicious tag flags are based on zero 2025 counts, >90% decline, >300% increase, raw issues, or missing panel/raw links.

## Final Recommendation

- DDD 2020-2025: yes
- Quarterly event study through Q4 2025: yes
- Donut-DiD excluding moderator-strike period: yes
- VOI/regret analysis: yes
