"""Number platform for Raven House Tools."""

from .entities import async_setup_numbers as async_setup_job_numbers
from .features import entry_supports_jobs


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Jobs number controls."""
    if entry_supports_jobs(config_entry):
        await async_setup_job_numbers(hass, config_entry, async_add_entities)
