"""Binary sensor platform for RC Jobs."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol
from croniter import CroniterBadCronError, croniter
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import (
    ATTR_CREATED,
    ATTR_CRON_EXPRESSION,
    ATTR_DAYS_INTERVAL,
    ATTR_IMAGE,
    ATTR_LAST_COMPLETED,
    ATTR_LAST_TRIGGERED,
    ATTR_PRIORITY,
    ATTR_TRIGGER_TYPE,
    DOMAIN,
    PREFIX_JOBS,
    SERVICE_COMPLETE_JOB,
    SERVICE_TRIGGER_JOB,
    STORAGE_VERSION,
    TRIGGER_TYPE_FREQUENCY,
    TRIGGER_TYPE_SCHEDULE,
)

_LOGGER = logging.getLogger(__name__)


def _jobs_storage_key(entry_id: str) -> str:
    return f"{DOMAIN}.jobs_{entry_id}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up job binary sensors from a config entry."""
    store = hass.helpers.storage.Store(hass, STORAGE_VERSION, _jobs_storage_key(config_entry.entry_id))
    jobs_data = await store.async_load() or {"jobs": []}

    entities: list[JobBinarySensor] = []
    for job_data in jobs_data.get("jobs", []):
        entities.append(JobBinarySensor(hass, config_entry, job_data, store))

    if entities:
        async_add_entities(entities)

    hass.data[DOMAIN][config_entry.entry_id]["jobs_store"] = store
    hass.data[DOMAIN][config_entry.entry_id]["jobs_entities"] = {
        entity.entity_id: entity for entity in entities
    }


async def async_setup_jobs_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register RC Jobs services."""

    async def async_trigger_job(call: ServiceCall) -> None:
        entity_id = call.data["entity_id"]
        async_dispatcher_send(hass, f"{DOMAIN}_trigger_{entity_id}")

    async def async_complete_job(call: ServiceCall) -> None:
        entity_id = call.data["entity_id"]
        async_dispatcher_send(hass, f"{DOMAIN}_complete_{entity_id}")

    schema = vol.Schema({vol.Required("entity_id"): cv.entity_id})

    if not hass.services.has_service(DOMAIN, SERVICE_TRIGGER_JOB):
        hass.services.async_register(
            DOMAIN,
            SERVICE_TRIGGER_JOB,
            async_trigger_job,
            schema=schema,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_COMPLETE_JOB):
        hass.services.async_register(
            DOMAIN,
            SERVICE_COMPLETE_JOB,
            async_complete_job,
            schema=schema,
        )


class JobBinarySensor(BinarySensorEntity):
    """Represents a job as a binary sensor (due/not due)."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        job_data: dict,
        store: Any,
    ) -> None:
        """Initialize the job sensor."""
        self.hass = hass
        self._store = store
        self._job_data = job_data

        self._attr_name = job_data["name"]
        self._attr_unique_id = f"{DOMAIN}_jobs_{config_entry.entry_id}_{job_data['id']}"
        self.entity_id = f"binary_sensor.{PREFIX_JOBS}_{job_data['id']}"

        self._trigger_type = job_data["trigger_type"]
        self._cron_expression = job_data.get("cron_expression")
        self._days_interval = job_data.get("days_interval")
        self._image = job_data.get("image")
        self._priority = job_data.get("priority", 0)

        self._is_due = False
        self._created = self._ensure_timezone_aware_iso(
            job_data.get("created", datetime.isoformat(utcnow()))
        )
        self._last_completed = job_data.get("last_completed")
        self._last_triggered = job_data.get("last_triggered")

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher signals."""
        self.async_write_ha_state()

        @callback
        def async_trigger_job() -> None:
            self._is_due = True
            self._last_triggered = datetime.isoformat(utcnow())
            self.async_write_ha_state()

        @callback
        def async_complete_job() -> None:
            self._is_due = False
            self._last_completed = datetime.isoformat(utcnow())
            self.async_write_ha_state()
            self.hass.async_create_task(self._save_job_state())

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_trigger_{self.entity_id}",
                async_trigger_job,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_complete_{self.entity_id}",
                async_complete_job,
            )
        )

    def update_attributes(self) -> None:
        """Update extra attributes."""
        self._attr_extra_state_attributes = {
            ATTR_TRIGGER_TYPE: self._trigger_type,
            ATTR_LAST_COMPLETED: self._last_completed,
            ATTR_LAST_TRIGGERED: self._last_triggered,
            ATTR_CREATED: self._created,
            ATTR_IMAGE: self._image,
            ATTR_PRIORITY: self._priority,
        }
        if self._trigger_type == TRIGGER_TYPE_SCHEDULE:
            self._attr_extra_state_attributes[ATTR_CRON_EXPRESSION] = self._cron_expression
        elif self._trigger_type == TRIGGER_TYPE_FREQUENCY:
            self._attr_extra_state_attributes[ATTR_DAYS_INTERVAL] = self._days_interval

    @property
    def is_on(self) -> bool:
        """Return True if the job is due."""
        self.update_attributes()
        self._check_if_due()
        return self._is_due

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:clipboard-check" if self._is_due else "mdi:clipboard"

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return "problem"

    def _check_if_due(self) -> None:
        if self._is_due:
            return

        if self._trigger_type == TRIGGER_TYPE_SCHEDULE and self._is_due_by_schedule():
            self._is_due = True
            self._last_triggered = datetime.isoformat(utcnow())
        elif self._trigger_type == TRIGGER_TYPE_FREQUENCY and self._is_due_by_frequency():
            self._is_due = True
            self._last_triggered = datetime.isoformat(utcnow())

    def _is_due_by_schedule(self) -> bool:
        if not self._cron_expression:
            return False

        try:
            now = utcnow()
            cron = croniter(self._cron_expression, now)
            last_occurrence = cron.get_prev(ret_type=datetime)

            if self._last_triggered:
                last_triggered = self._ensure_timezone_aware_datetime(self._last_triggered)
                return last_triggered < last_occurrence
            return True
        except (CroniterBadCronError, ValueError, TypeError) as err:
            _LOGGER.error("Error checking schedule for %s: %s", self._attr_name, err)
            return False

    def _is_due_by_frequency(self) -> bool:
        if not self._days_interval or self._days_interval <= 0:
            return False
        if not self._last_completed:
            return True

        try:
            last_completed = self._ensure_timezone_aware_datetime(self._last_completed)
            due_date = last_completed + timedelta(days=self._days_interval)
            return utcnow() >= due_date
        except (OverflowError, TypeError, ValueError) as err:
            _LOGGER.error("Error checking frequency for %s: %s", self._attr_name, err)
            return False

    def _ensure_timezone_aware_datetime(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=utcnow().tzinfo)
        return parsed

    def _ensure_timezone_aware_iso(self, value: str) -> str:
        return self._ensure_timezone_aware_datetime(value).isoformat()

    async def _save_job_state(self) -> None:
        jobs_data = await self._store.async_load() or {"jobs": []}
        job_index = next(
            (index for index, job in enumerate(jobs_data["jobs"]) if job["id"] == self._job_data["id"]),
            None,
        )

        if job_index is not None:
            jobs_data["jobs"][job_index]["last_completed"] = self._last_completed
            jobs_data["jobs"][job_index]["last_triggered"] = self._last_triggered
            await self._store.async_save(jobs_data)
