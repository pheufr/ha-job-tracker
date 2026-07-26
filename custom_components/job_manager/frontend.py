"""Frontend setup for Job Manager."""
import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

CARD_VERSION = "0.1.0"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Set up frontend elements."""
    _LOGGER.debug(
        "Skipping custom card registration: custom_components/job_manager/job_manager_card.js is not present"
    )
