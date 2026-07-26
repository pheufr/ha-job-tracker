"""
Raven Castle Integration for Home Assistant.

A multi-feature home automation toolkit providing:
- RC Jobs: Track and manage recurring jobs/tasks
- RC Quiz: Interactive quiz system (future feature)

Entity naming convention: {platform}.{feature_prefix}_{entity_id}
"""
import logging
from datetime import timedelta
from typing import Final

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, PREFIX_JOBS, FEATURE_JOBS, SERVICE_TRIGGER_JOB, SERVICE_COMPLETE_JOB

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Raven Castle integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry from job_manager to raven_castle."""
    _LOGGER.info(
        "Migrating Raven Castle config entry from version %s", config_entry.version
    )

    if config_entry.version == 1:
        entity_registry = er.async_get(hass)

        # Migrate entity IDs from job_manager_* to rc_jobs_*
        entities = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        for entity in entities:
            if entity.entity_id.startswith("binary_sensor.job_manager_"):
                job_id = entity.entity_id.replace("binary_sensor.job_manager_", "")
                new_entity_id = f"binary_sensor.{PREFIX_JOBS}_{job_id}"
                _LOGGER.info(
                    "Migrating entity %s to %s", entity.entity_id, new_entity_id
                )
                entity_registry.async_update_entity(
                    entity.entity_id,
                    new_entity_id=new_entity_id,
                )

        # Migrate storage data from old job_manager key to raven_castle key
        old_store = hass.helpers.storage.Store(
            hass, 1, f"job_manager.jobs_{config_entry.entry_id}"
        )
        new_store = hass.helpers.storage.Store(
            hass, 1, f"{DOMAIN}.jobs_{config_entry.entry_id}"
        )
        old_data = await old_store.async_load()
        if old_data:
            await new_store.async_save(old_data)
            _LOGGER.info(
                "Migrated job data from job_manager storage to raven_castle storage"
            )

        hass.config_entries.async_update_entry(config_entry, version=2)
        _LOGGER.info("Migration to Raven Castle completed successfully")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Raven Castle from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (once for all entries)
    async def async_trigger_job(call: ServiceCall) -> None:
        """Trigger a job immediately."""
        job_entity_id = call.data.get("entity_id")
        if not job_entity_id:
            _LOGGER.error("No entity_id provided for trigger_job service")
            return

        entity = hass.states.get(job_entity_id)
        if not entity:
            _LOGGER.error("Entity %s not found", job_entity_id)
            return

        _LOGGER.info("Triggering job: %s", job_entity_id)
        async_dispatcher_send(hass, f"{DOMAIN}_trigger_{job_entity_id}")

    async def async_complete_job(call: ServiceCall) -> None:
        """Mark a job as completed."""
        job_entity_id = call.data.get("entity_id")
        if not job_entity_id:
            _LOGGER.error("No entity_id provided for complete_job service")
            return

        entity = hass.states.get(job_entity_id)
        if not entity:
            _LOGGER.error("Entity %s not found", job_entity_id)
            return

        _LOGGER.info("Completing job: %s", job_entity_id)
        async_dispatcher_send(hass, f"{DOMAIN}_complete_{job_entity_id}")

    if not hass.services.has_service(DOMAIN, SERVICE_TRIGGER_JOB):
        hass.services.async_register(
            DOMAIN,
            SERVICE_TRIGGER_JOB,
            async_trigger_job,
            schema=vol.Schema({
                vol.Required("entity_id"): cv.entity_id,
            }),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_COMPLETE_JOB):
        hass.services.async_register(
            DOMAIN,
            SERVICE_COMPLETE_JOB,
            async_complete_job,
            schema=vol.Schema({
                vol.Required("entity_id"): cv.entity_id,
            }),
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
