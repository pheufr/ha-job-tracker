"""Helpers for feature-scoped config entries."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_FEATURE, FEATURE_BOTH, FEATURE_JOBS, FEATURE_QUIZ


def get_entry_feature(config_entry: ConfigEntry) -> str:
    """Return the feature mode for a config entry."""
    return config_entry.data.get(CONF_FEATURE, FEATURE_BOTH)


def entry_supports_jobs(config_entry: ConfigEntry) -> bool:
    """Return whether an entry exposes jobs."""
    return get_entry_feature(config_entry) in (FEATURE_BOTH, FEATURE_JOBS)


def entry_supports_quiz(config_entry: ConfigEntry) -> bool:
    """Return whether an entry exposes quiz."""
    return get_entry_feature(config_entry) in (FEATURE_BOTH, FEATURE_QUIZ)


def entry_id_supports_jobs(hass: HomeAssistant, entry_id: str) -> bool:
    """Return whether a loaded entry ID exposes jobs."""
    config_entry = hass.config_entries.async_get_entry(entry_id)
    return bool(config_entry and entry_supports_jobs(config_entry))


def entry_id_supports_quiz(hass: HomeAssistant, entry_id: str) -> bool:
    """Return whether a loaded entry ID exposes quiz."""
    config_entry = hass.config_entries.async_get_entry(entry_id)
    return bool(config_entry and entry_supports_quiz(config_entry))
