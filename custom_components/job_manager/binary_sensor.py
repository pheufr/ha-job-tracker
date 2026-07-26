"""Binary sensor for Job Manager."""
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from croniter import croniter
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from .const import (
    DOMAIN,
    TRIGGER_TYPE_SCHEDULE,
    TRIGGER_TYPE_FREQUENCY,
    ATTR_TRIGGER_TYPE,
    ATTR_CRON_EXPRESSION,
    ATTR_DAYS_INTERVAL,
    ATTR_LAST_COMPLETED,
    ATTR_CREATED,
    ATTR_LAST_TRIGGERED,
    ATTR_IMAGE,
    ATTR_PRIORITY,
    SERVICE_TRIGGER_JOB,
    SERVICE_COMPLETE_JOB,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from a config entry."""
    # Load jobs from storage
    store = hass.helpers.storage.Store(hass, 1, f"{DOMAIN}.jobs_{config_entry.entry_id}")
    jobs_data = await store.async_load() or {"jobs": []}

    entities = []
    for job_data in jobs_data.get("jobs", []):
        job = JobBinarySensor(hass, config_entry, job_data, store)
        entities.append(job)

    if entities:
        async_add_entities(entities)

    # Store reference for adding new jobs dynamically
    hass.data[DOMAIN][config_entry.entry_id]["async_add_entities"] = async_add_entities
    hass.data[DOMAIN][config_entry.entry_id]["store"] = store
    hass.data[DOMAIN][config_entry.entry_id]["jobs"] = {e.entity_id: e for e in entities}


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
        self._config_entry = config_entry
        self._store = store
        self._job_data = job_data

        self._attr_name = job_data["name"]
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_{job_data['id']}"
        self.entity_id = f"binary_sensor.{DOMAIN}_{job_data['id']}"

        # Job configuration
        self._trigger_type = job_data["trigger_type"]
        self._cron_expression = job_data.get("cron_expression")  # For schedule type
        self._days_interval = job_data.get("days_interval")  # For frequency type
        self._image = job_data.get("image")  # Image URL
        self._priority = job_data.get("priority", 0)  # Priority level

        # Job state
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
            """Trigger job callback."""
            self._is_due = True
            self._last_triggered = datetime.isoformat(utcnow())
            self.async_write_ha_state()
            _LOGGER.info(f"Job triggered: {self._attr_name}")

        @callback
        def async_complete_job() -> None:
            """Complete job callback."""
            self._is_due = False
            self._last_completed = datetime.isoformat(utcnow())
            self.async_write_ha_state()
            self._save_job_state()
            _LOGGER.info(f"Job completed: {self._attr_name}")

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
        self._check_if_due()
        return "mdi:clipboard-check" if self._is_due else "mdi:clipboard"

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return "problem"

    def _check_if_due(self) -> None:
        """Check if the job should be marked as due."""
        if self._is_due:
            # Already due, don't change state
            return

        if self._trigger_type == TRIGGER_TYPE_SCHEDULE:
            if self._is_due_by_schedule():
                self._is_due = True
                self._last_triggered = datetime.isoformat(utcnow())
        elif self._trigger_type == TRIGGER_TYPE_FREQUENCY:
            if self._is_due_by_frequency():
                self._is_due = True
                self._last_triggered = datetime.isoformat(utcnow())

    def _is_due_by_schedule(self) -> bool:
        """Check if job is due based on cron schedule."""
        if not self._cron_expression:
            return False

        try:
            now = utcnow()
            cron = croniter(self._cron_expression, now)
            last_occurrence = cron.get_prev(ret_type=datetime)

            if self._last_triggered:
                last_triggered = datetime.fromisoformat(self._last_triggered)
                if last_triggered.tzinfo is None:
                    last_triggered = last_triggered.replace(tzinfo=utcnow().tzinfo)
                return last_triggered < last_occurrence
            else:
                # Never been triggered, check if it's past the first occurrence
                return True
        except Exception as e:
            _LOGGER.error(f"Error checking schedule for {self._attr_name}: {e}")
            return False

    def _is_due_by_frequency(self) -> bool:
        """Check if job is due based on frequency interval."""
        if not self._days_interval or self._days_interval <= 0:
            return False

        if not self._last_completed:
            # Never completed, so it's due
            return True

        try:
            last_completed = datetime.fromisoformat(self._last_completed)
            if last_completed.tzinfo is None:
                last_completed = last_completed.replace(tzinfo=utcnow().tzinfo)
            due_date = last_completed + timedelta(days=self._days_interval)
            return utcnow() >= due_date
        except Exception as e:
            _LOGGER.error(f"Error checking frequency for {self._attr_name}: {e}")
            return False

    def _ensure_timezone_aware_iso(self, value: str) -> str:
        """Return an ISO datetime string with timezone information."""
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=utcnow().tzinfo)
        return parsed.isoformat()

    async def _save_job_state(self) -> None:
        """Save job state to storage."""
        jobs_data = await self._store.async_load() or {"jobs": []}
        job_index = next(
            (i for i, j in enumerate(jobs_data["jobs"]) if j["id"] == self._job_data["id"]),
            None,
        )

        if job_index is not None:
            jobs_data["jobs"][job_index]["last_completed"] = self._last_completed
            jobs_data["jobs"][job_index]["last_triggered"] = self._last_triggered
            await self._store.async_save(jobs_data)
