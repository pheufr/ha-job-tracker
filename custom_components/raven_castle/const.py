"""Constants for the Raven Castle integration."""

DOMAIN = "raven_castle"

# Feature identifiers
FEATURE_JOBS = "jobs"
FEATURE_QUIZ = "quiz"

# Entity naming prefixes
PREFIX_JOBS = "rc_jobs"
PREFIX_QUIZ = "rc_quiz"

# RC Jobs - Job trigger types
TRIGGER_TYPE_SCHEDULE = "schedule"
TRIGGER_TYPE_FREQUENCY = "frequency"

# RC Jobs - Attribute names
ATTR_TRIGGER_TYPE = "trigger_type"
ATTR_CRON_EXPRESSION = "cron_expression"
ATTR_DAYS_INTERVAL = "days_interval"
ATTR_LAST_COMPLETED = "last_completed"
ATTR_CREATED = "created"
ATTR_LAST_TRIGGERED = "last_triggered"
ATTR_IMAGE = "image"
ATTR_PRIORITY = "priority"

# RC Jobs - Service names
SERVICE_TRIGGER_JOB = "trigger_job"
SERVICE_COMPLETE_JOB = "complete_job"
