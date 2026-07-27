"""Sensor platform for Raven Castle Tools."""

from .entities import async_setup_sensors as async_setup_job_sensors
from .quiz_entities import async_setup_sensors as async_setup_quiz_sensors


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
	"""Set up Jobs and Quiz sensors."""
	await async_setup_job_sensors(hass, config_entry, async_add_entities)
	await async_setup_quiz_sensors(hass, config_entry, async_add_entities)