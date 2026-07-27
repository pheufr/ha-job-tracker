"""Constants for Raven Castle Jobs."""

DOMAIN = "raven_castle_jobs"

PREFIX_JOBS = "rc_jobs"
STORAGE_VERSION = 1

TRIGGER_TYPE_SCHEDULE = "schedule"
TRIGGER_TYPE_FREQUENCY = "frequency"

ATTR_TRIGGER_TYPE = "trigger_type"
ATTR_CRON_EXPRESSION = "cron_expression"
ATTR_DAYS_INTERVAL = "days_interval"
ATTR_LAST_COMPLETED = "last_completed"
ATTR_CREATED = "created"
ATTR_LAST_TRIGGERED = "last_triggered"
ATTR_IMAGE = "image"
ATTR_PRIORITY = "priority"
ATTR_NEXT_DUE = "next_due"
ATTR_JOB_ID = "job_id"
ATTR_ENTITY_ROLE = "entity_role"

SERVICE_TRIGGER_JOB = "trigger_job"
SERVICE_COMPLETE_JOB = "complete_job"

JOBS_SIGNAL_UPDATE = f"{DOMAIN}_job_update"