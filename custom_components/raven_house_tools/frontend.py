"""Frontend setup for Raven House Tools."""

from __future__ import annotations

import logging
from pathlib import Path
import json

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_CARD_FILES = [
    "rh-jobs-card.js",
    "rh-quiz-leaderboard-card.js",
    "rh-quiz-master-card.js",
]


def _integration_version() -> str:
    """Read manifest version for frontend cache busting."""
    manifest_path = Path(__file__).parent / "manifest.json"
    try:
        with manifest_path.open("r", encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)
        return str(manifest.get("version", "dev"))
    except (OSError, ValueError, TypeError) as err:
        _LOGGER.debug("Could not read integration version from manifest: %s", err)
        return "dev"


def _assets_revision(static_path: Path) -> str:
    """Build a cache-busting token from card file mtimes."""
    timestamps: list[int] = []
    for card_file in _CARD_FILES:
        try:
            timestamps.append(int((static_path / card_file).stat().st_mtime))
        except OSError:
            continue
    if not timestamps:
        return _integration_version()
    return f"{_integration_version()}-{max(timestamps)}"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Register static paths and Lovelace module URLs for custom cards."""
    static_url = "/raven_house_tools"
    module_base_absolute = "/raven_house_tools"
    static_path = Path(__file__).parent / "www"

    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(static_url, str(static_path), False)]
        )
    except Exception as err:  # noqa: BLE001
        # Happens when this URL is already registered during repeated setup paths.
        _LOGGER.debug("Static path %s already registered: %s", static_url, err)
    _LOGGER.debug("Registered Raven House Tools card assets at %s", static_url)
    version = _assets_revision(static_path)

    for card_file in _CARD_FILES:
        versioned_absolute = f"{module_base_absolute}/{card_file}?v={version}"
        add_extra_js_url(hass, versioned_absolute)
        _LOGGER.debug("Registered Lovelace module URL: %s", versioned_absolute)

        # Compatibility fallback for frontend builds that do not honor querystring resources.
        plain_absolute = f"{module_base_absolute}/{card_file}"
        add_extra_js_url(hass, plain_absolute)
        _LOGGER.debug("Registered Lovelace module URL fallback: %s", plain_absolute)
