"""Binary sensor platform for Raven House Tools."""

from .entities import async_setup_binary_sensors as async_setup_job_binary_sensors
from .quiz_entities import async_setup_binary_sensors as async_setup_quiz_binary_sensors


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
	"""Set up Jobs and Quiz binary sensors."""
	await async_setup_job_binary_sensors(hass, config_entry, async_add_entities)
	await async_setup_quiz_binary_sensors(hass, config_entry, async_add_entities)
