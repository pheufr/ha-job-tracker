"""Text platform for Raven House Tools."""

from .entities import async_setup_texts as async_setup_job_texts
from .quiz_entities import async_setup_texts as async_setup_quiz_texts


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Jobs and Quiz text controls."""
    await async_setup_job_texts(hass, config_entry, async_add_entities)
    await async_setup_quiz_texts(hass, config_entry, async_add_entities)
