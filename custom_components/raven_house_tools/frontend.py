"""Frontend setup for Raven House Tools."""

from __future__ import annotations

import logging
from pathlib import Path
import json

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_FRONTEND_REGISTERED_KEY = f"{DOMAIN}_frontend_registered"

_STATIC_URL_CANDIDATES = [
    "/local/raven_house_tools",
    "/raven_house_tools",
]

_CARD_FILES = [
    "rh-jobs-card.js",
    "rh-quiz-card.js",
    "rh-quiz-master-card.js",
    "rh-quiz-round-card.js",
    "rh-soundboard-card.js",
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


def _compute_assets_revision(static_path: Path) -> str:
    """Compute frontend asset revision in a worker thread."""
    return _assets_revision(static_path)


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Register static paths and Lovelace module URLs for custom cards.

    Safe to call multiple times — a guard flag ensures registration only
    happens once per Home Assistant lifecycle.
    """
    if hass.data.get(_FRONTEND_REGISTERED_KEY):
        _LOGGER.debug("Raven House Tools frontend already registered, skipping")
        return

    static_path = Path(__file__).parent / "www"
    registered_urls: list[str] = []

    for static_url in _STATIC_URL_CANDIDATES:
        try:
            await hass.http.async_register_static_paths(
                [StaticPathConfig(static_url, str(static_path), False)]
            )
            _LOGGER.debug(
                "Registered Raven House Tools card assets at %s", static_url
            )
            registered_urls.append(static_url)
        except Exception as err:  # noqa: BLE001
            # Expected when Home Assistant already has this route in place.
            _LOGGER.debug("Static path %s not newly registered: %s", static_url, err)
            if "already" in str(err).lower():
                registered_urls.append(static_url)

    if not registered_urls:
        _LOGGER.error(
            "Could not register any Raven House Tools static card paths; cards will not load"
        )
        return

    # Prefer /local/* URLs because they are the most broadly compatible with
    # kiosk/cast/no-cache frontend contexts.
    preferred_static_url = registered_urls[0]
    version = await hass.async_add_executor_job(_compute_assets_revision, static_path)

    for card_file in _CARD_FILES:
        url = f"{preferred_static_url}/{card_file}?v={version}"
        add_extra_js_url(hass, url)
        _LOGGER.debug("Registered Lovelace module URL: %s", url)

    hass.data[_FRONTEND_REGISTERED_KEY] = True
