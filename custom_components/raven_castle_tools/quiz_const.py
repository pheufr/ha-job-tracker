"""Constants for Raven Castle Tools quiz support."""

DOMAIN = "raven_castle_tools"

PREFIX_QUIZ = "rc_quiz"
STORAGE_VERSION = 1

ATTR_PLAYER_NAME = "player_name"
ATTR_PLAYER_ALIAS = "player_alias"
ATTR_PLAYER_PHOTO = "player_photo"
ATTR_TOTAL_SCORE = "total_score"
ATTR_ROUND_SCORE = "current_round_score"
ATTR_LAST_ROUND_SCORE = "last_round_score"
ATTR_PLAYER_ENABLED = "enabled"
ATTR_PLAYER_ID = "player_id"
ATTR_PLAYER_METRIC = "player_metric"
ATTR_CREATED = "created"

SERVICE_ADD_PLAYER = "add_player"
SERVICE_REMOVE_PLAYER = "remove_player"
SERVICE_ENABLE_PLAYER = "enable_player"
SERVICE_DISABLE_PLAYER = "disable_player"
SERVICE_ADD_POINTS = "add_points"
SERVICE_REMOVE_POINTS = "remove_points"
SERVICE_START_NEW_ROUND = "start_new_round"
SERVICE_START_NEW_QUIZ = "start_new_quiz"
SERVICE_RESET_QUIZ = "reset_quiz"

QUIZ_SIGNAL_UPDATE = f"{DOMAIN}_player_update"