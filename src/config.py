from datetime import date


CHATGPT_RELEASE_DATE = date(2022, 11, 30)
PRE_PERIOD_END = CHATGPT_RELEASE_DATE

DEFAULT_NEW_USER_DAYS = 365
DEFAULT_LOW_REPUTATION_THRESHOLD = 100
DEFAULT_SHORT_BODY_CHARS = 750

EXPECTED_STACKOVERFLOW_FILES = {
    "tag_week": "stackoverflow_tag_week.csv",
    "user_tag_week": "stackoverflow_user_tag_week.csv",
    "post_complexity": "stackoverflow_post_complexity.csv",
}
