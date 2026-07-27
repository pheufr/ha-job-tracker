"""Constants for Raven House Tools jobs support."""

DOMAIN = "raven_house_tools"

CONF_FEATURE = "feature"
FEATURE_BOTH = "both"
FEATURE_JOBS = "jobs"
FEATURE_QUIZ = "quiz"

PREFIX_JOBS = "rh_jobs"
STORAGE_VERSION = 1

TRIGGER_TYPE_SCHEDULE = "schedule"
TRIGGER_TYPE_FREQUENCY = "frequency"
TRIGGER_TYPE_MANUAL = "manual"

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
SERVICE_DISMISS_JOB = "dismiss_job"
SERVICE_RENAME_JOB = "rename_job"
SERVICE_UPDATE_JOB_IMAGE = "update_job_image"
SERVICE_ADD_JOB = "add_job"

SERVICE_SOUNDBOARD_CONNECT = "soundboard_connect"
SERVICE_SOUNDBOARD_DISCONNECT = "soundboard_disconnect"
SERVICE_SOUNDBOARD_PLAY_CLIP = "soundboard_play_clip"
SERVICE_SOUNDBOARD_SET_TARGET = "soundboard_set_target"

JOBS_SIGNAL_UPDATE = f"{DOMAIN}_job_update"
