"""The Job Manager integration."""
import logging
from datetime import timedelta
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import (
    SERVICE_RELOAD,
)

from .config_flow import JobManagerOptionsFlow

_LOGGER = logging.getLogger(__name__)

DOMAIN = "job_manager"
PLATFORM = "job_manager"
SCAN_INTERVAL = timedelta(minutes=1)

SERVICE_TRIGGER_JOB: Final = "trigger_job"
SERVICE_COMPLETE_JOB: Final = "complete_job"

PLATFORMS = ["binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Job Manager integration."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Job Manager from a config entry."""
    hass.data[DOMAIN][entry.entry_id] = {}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    async def async_trigger_job(call: ServiceCall) -> None:
        """Trigger a job immediately."""
        job_entity_id = call.data.get("entity_id")
        if not job_entity_id:
            _LOGGER.error("No entity_id provided for trigger_job service")
            return

        entity = hass.states.get(job_entity_id)
        if not entity:
            _LOGGER.error(f"Entity {job_entity_id} not found")
            return

        _LOGGER.info(f"Triggering job: {job_entity_id}")
        from homeassistant.helpers.dispatcher import async_dispatcher_send
        async_dispatcher_send(hass, f"{DOMAIN}_trigger_{job_entity_id}")

    async def async_complete_job(call: ServiceCall) -> None:
        """Mark a job as completed."""
        job_entity_id = call.data.get("entity_id")
        if not job_entity_id:
            _LOGGER.error("No entity_id provided for complete_job service")
            return

        entity = hass.states.get(job_entity_id)
        if not entity:
            _LOGGER.error(f"Entity {job_entity_id} not found")
            return

        _LOGGER.info(f"Completing job: {job_entity_id}")
        from homeassistant.helpers.dispatcher import async_dispatcher_send
        async_dispatcher_send(hass, f"{DOMAIN}_complete_{job_entity_id}")

    if not hass.services.has_service(DOMAIN, SERVICE_TRIGGER_JOB):
        hass.services.async_register(
            DOMAIN,
            SERVICE_TRIGGER_JOB,
            async_trigger_job,
            schema=None,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_COMPLETE_JOB):
        hass.services.async_register(
            DOMAIN,
            SERVICE_COMPLETE_JOB,
            async_complete_job,
            schema=None,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


@config_entries.register_options_flow
class JobManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Job Manager."""

    async_get_options_flow = staticmethod(
        lambda config_entry: JobManagerOptionsFlow(config_entry)
    )
