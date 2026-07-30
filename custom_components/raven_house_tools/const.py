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
ATTR_ICON = "icon"
ATTR_COLOUR = "colour"
ATTR_JOB_ICON = "job_icon"
ATTR_JOB_COLOUR = "job_colour"
ATTR_PRIORITY = "priority"
ATTR_NEXT_DUE = "next_due"
ATTR_JOB_ID = "job_id"
ATTR_ENTITY_ROLE = "entity_role"

SERVICE_TRIGGER_JOB = "trigger_job"
SERVICE_COMPLETE_JOB = "complete_job"
SERVICE_DISMISS_JOB = "dismiss_job"
SERVICE_RENAME_JOB = "rename_job"
SERVICE_UPDATE_JOB_IMAGE = "update_job_image"
SERVICE_UPDATE_JOB_ICON = "update_job_icon"
SERVICE_UPDATE_JOB_COLOUR = "update_job_colour"
SERVICE_ADD_JOB = "add_job"

SERVICE_SOUNDBOARD_CONNECT = "soundboard_connect"
SERVICE_SOUNDBOARD_DISCONNECT = "soundboard_disconnect"
SERVICE_SOUNDBOARD_PLAY_CLIP = "soundboard_play_clip"
SERVICE_SOUNDBOARD_SET_TARGET = "soundboard_set_target"
SERVICE_SOUNDBOARD_SET_MODE = "soundboard_set_mode"

JOBS_SIGNAL_UPDATE = f"{DOMAIN}_job_update"
