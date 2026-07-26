"""Custom frontend resources for Raven Castle integration."""
import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Set up frontend elements."""
    # Register static paths for custom cards
    # Commented out until cards are fully implemented
    # hass.http.register_static_path(
    #     "/raven_castle_static/rc-jobs-card.js",
    #     hass.config.path("custom_components/raven_castle/www/rc-jobs-card.js"),
    #     cache_headers=False,
    # )
    pass
