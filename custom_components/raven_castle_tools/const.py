"""Constants for the Raven Castle Tools integration."""

DOMAIN = "raven_castle_tools"

FEATURE_JOBS = "jobs"
FEATURE_QUIZ = "quiz"

PREFIX_JOBS = "rc_jobs"
PREFIX_QUIZ = "rc_quiz"

STORAGE_VERSION = 1

# Job trigger types
TRIGGER_TYPE_SCHEDULE = "schedule"
TRIGGER_TYPE_FREQUENCY = "frequency"

# Job attribute names
ATTR_TRIGGER_TYPE = "trigger_type"
ATTR_CRON_EXPRESSION = "cron_expression"
ATTR_DAYS_INTERVAL = "days_interval"
ATTR_LAST_COMPLETED = "last_completed"
ATTR_CREATED = "created"
ATTR_LAST_TRIGGERED = "last_triggered"
ATTR_IMAGE = "image"
ATTR_PRIORITY = "priority"

# Quiz attribute names
ATTR_PLAYER_NAME = "player_name"
ATTR_PLAYER_ALIAS = "player_alias"
ATTR_PLAYER_PHOTO = "player_photo"
ATTR_TOTAL_SCORE = "total_score"
ATTR_ROUND_SCORE = "current_round_score"
ATTR_LAST_ROUND_SCORE = "last_round_score"
ATTR_PLAYER_ENABLED = "enabled"

# Service names
SERVICE_TRIGGER_JOB = "trigger_job"
SERVICE_COMPLETE_JOB = "complete_job"
SERVICE_ADD_PLAYER = "add_player"
SERVICE_REMOVE_PLAYER = "remove_player"
SERVICE_ENABLE_PLAYER = "enable_player"
SERVICE_DISABLE_PLAYER = "disable_player"
SERVICE_ADD_POINTS = "add_points"
SERVICE_REMOVE_POINTS = "remove_points"
SERVICE_START_NEW_ROUND = "start_new_round"
SERVICE_START_NEW_QUIZ = "start_new_quiz"
SERVICE_RESET_QUIZ = "reset_quiz"
