"""Text platform for Raven House Tools."""

from .entities import async_setup_texts as async_setup_job_texts
from .features import entry_supports_jobs, entry_supports_quiz
from .quiz_entities import async_setup_texts as async_setup_quiz_texts


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Jobs and Quiz text controls."""
    if entry_supports_jobs(config_entry):
        await async_setup_job_texts(hass, config_entry, async_add_entities)
    if entry_supports_quiz(config_entry):
        await async_setup_quiz_texts(hass, config_entry, async_add_entities)
