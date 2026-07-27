"""Select platform for Raven House Tools."""

from .entities import async_setup_selects as async_setup_job_selects


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Jobs select controls."""
    await async_setup_job_selects(hass, config_entry, async_add_entities)
