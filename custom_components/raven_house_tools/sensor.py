"""Sensor platform for Raven House Tools."""

from .entities import async_setup_sensors as async_setup_job_sensors
from .features import entry_supports_jobs, entry_supports_quiz
from .quiz_entities import async_setup_sensors as async_setup_quiz_sensors


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
	"""Set up Jobs and Quiz sensors."""
	if entry_supports_jobs(config_entry):
		await async_setup_job_sensors(hass, config_entry, async_add_entities)
	if entry_supports_quiz(config_entry):
		await async_setup_quiz_sensors(hass, config_entry, async_add_entities)
