"""Frontend setup for Raven Castle Quiz."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_CARD_FILES = [
    "rc-quiz-leaderboard-card.js",
    "rc-quiz-master-card.js",
]


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Register static paths and Lovelace module URLs for custom cards."""
    static_url = "/raven_castle_quiz"
    static_path = Path(__file__).parent / "www"

    await hass.http.async_register_static_paths(
        [StaticPathConfig(static_url, str(static_path), False)]
    )
    _LOGGER.debug("Registered Raven Castle Quiz card assets at %s", static_url)

    for card_file in _CARD_FILES:
        url = f"{static_url}/{card_file}"
        add_extra_js_url(hass, url)
        _LOGGER.debug("Registered Lovelace module URL: %s", url)