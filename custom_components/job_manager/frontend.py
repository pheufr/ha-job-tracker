"""Custom card for displaying images of due jobs."""
import logging
from typing import Any

from homeassistant.components.frontend import (
    DOMAIN as FRONTEND_DOMAIN,
)
from homeassistant.components.lovelace import CUSTOM_TYPE_PREFIX
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

CARD_VERSION = "0.1.0"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Set up frontend elements."""
    hass.http.register_static_path(
        "/static/job-manager-card.js",
        hass.config.path("custom_components/job_manager/job_manager_card.js"),
        cache_headers=False,
    )
