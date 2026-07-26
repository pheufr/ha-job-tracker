"""Frontend setup for Raven Castle Tools."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Register static paths for custom cards."""
    static_url = "/raven_castle_tools"
    static_path = Path(__file__).parent / "www"

    await hass.http.async_register_static_paths(
        [StaticPathConfig(static_url, str(static_path), False)]
    )
    _LOGGER.debug("Registered Raven Castle Tools card assets at %s", static_url)
