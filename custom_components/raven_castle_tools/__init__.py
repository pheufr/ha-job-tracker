"""The Raven Castle Tools integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .binary_sensor import async_setup_jobs_services
from .const import (
    DOMAIN,
    SERVICE_ADD_PLAYER,
    SERVICE_ADD_POINTS,
    SERVICE_COMPLETE_JOB,
    SERVICE_DISABLE_PLAYER,
    SERVICE_ENABLE_PLAYER,
    SERVICE_REMOVE_PLAYER,
    SERVICE_REMOVE_POINTS,
    SERVICE_RESET_QUIZ,
    SERVICE_START_NEW_QUIZ,
    SERVICE_START_NEW_ROUND,
    SERVICE_TRIGGER_JOB,
)
from .frontend import async_setup_frontend
from .quiz import async_setup_quiz_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Raven Castle Tools integration."""
    hass.data.setdefault(DOMAIN, {})
    await async_setup_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Raven Castle Tools from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await async_setup_jobs_services(hass, entry)
    await async_setup_quiz_services(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    if not hass.data.get(DOMAIN):
        for service in (
            SERVICE_TRIGGER_JOB,
            SERVICE_COMPLETE_JOB,
            SERVICE_ADD_PLAYER,
            SERVICE_REMOVE_PLAYER,
            SERVICE_ENABLE_PLAYER,
            SERVICE_DISABLE_PLAYER,
            SERVICE_ADD_POINTS,
            SERVICE_REMOVE_POINTS,
            SERVICE_START_NEW_ROUND,
            SERVICE_START_NEW_QUIZ,
            SERVICE_RESET_QUIZ,
        ):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entity IDs for renamed RC Jobs prefix."""
    if entry.version >= 2:
        return True

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    for entity_entry in entries:
        old_entity_id = entity_entry.entity_id
        new_entity_id = old_entity_id

        if old_entity_id.startswith("binary_sensor.rc_job_manager_"):
            new_entity_id = old_entity_id.replace(
                "binary_sensor.rc_job_manager_",
                "binary_sensor.rc_jobs_",
                1,
            )
        elif old_entity_id.startswith("binary_sensor.job_manager_"):
            suffix = old_entity_id[len("binary_sensor.job_manager_") :]
            new_entity_id = f"binary_sensor.rc_jobs_{suffix}"

        if new_entity_id != old_entity_id:
            try:
                entity_registry.async_update_entity(
                    old_entity_id,
                    new_entity_id=new_entity_id,
                )
                _LOGGER.info("Migrated entity id %s -> %s", old_entity_id, new_entity_id)
            except ValueError:
                _LOGGER.warning(
                    "Could not migrate entity id %s to %s", old_entity_id, new_entity_id
                )

    hass.config_entries.async_update_entry(entry, version=2)
    _LOGGER.info("Migrated Raven Castle Tools config entry %s to version 2", entry.entry_id)
    return True
