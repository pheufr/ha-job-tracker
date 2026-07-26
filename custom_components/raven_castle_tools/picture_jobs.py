"""Picture Jobs card for displaying job images."""
import logging
from datetime import datetime
from typing import Any, Optional

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import (
    DOMAIN,
    TRIGGER_TYPE_SCHEDULE,
    TRIGGER_TYPE_FREQUENCY,
    ATTR_TRIGGER_TYPE,
    ATTR_CRON_EXPRESSION,
    ATTR_DAYS_INTERVAL,
    ATTR_LAST_COMPLETED,
    ATTR_CREATED,
    ATTR_LAST_TRIGGERED,
    ATTR_IMAGE,
    ATTR_PRIORITY,
)

_LOGGER = logging.getLogger(__name__)
