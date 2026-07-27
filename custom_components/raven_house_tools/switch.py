"""Switch platform for Raven House Tools."""

from .features import entry_supports_quiz
from .quiz_entities import async_setup_switches as async_setup_quiz_switches


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Quiz switches."""
    if entry_supports_quiz(config_entry):
        await async_setup_quiz_switches(hass, config_entry, async_add_entities)
