"""Switch platform for Raven House Tools."""

from .entities import async_setup_switches as async_setup_job_switches
from .quiz_entities import async_setup_switches as async_setup_quiz_switches


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Jobs and Quiz switches."""
    await async_setup_job_switches(hass, config_entry, async_add_entities)
    await async_setup_quiz_switches(hass, config_entry, async_add_entities)
