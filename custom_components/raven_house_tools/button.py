"""Button platform for Raven House Tools."""

from .quiz_entities import async_setup_buttons as async_setup_quiz_buttons


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Quiz buttons."""
    await async_setup_quiz_buttons(hass, config_entry, async_add_entities)
