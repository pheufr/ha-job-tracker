"""Entity model for Raven Castle Jobs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

import voluptuous as vol
from croniter import CroniterBadCronError, croniter
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import utcnow

from .const import (
    ATTR_CREATED,
    ATTR_CRON_EXPRESSION,
    ATTR_DAYS_INTERVAL,
    ATTR_ENTITY_ROLE,
    ATTR_IMAGE,
    ATTR_JOB_ID,
    ATTR_LAST_COMPLETED,
    ATTR_LAST_TRIGGERED,
    ATTR_NEXT_DUE,
    ATTR_PRIORITY,
    ATTR_TRIGGER_TYPE,
    DOMAIN,
    JOBS_SIGNAL_UPDATE,
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


def _entry_data(hass: HomeAssistant, entry_id: str) -> dict[str, Any]:
    return hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})


def _normalize_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job["id"],
        "name": job.get("name", ""),
        "trigger_type": job.get("trigger_type", TRIGGER_TYPE_SCHEDULE),
        "cron_expression": job.get("cron_expression"),
        "days_interval": job.get("days_interval"),
        "image": job.get("image", ""),
        "priority": int(job.get("priority", 0)),
        "created": _ensure_timezone_aware_iso(job.get("created") or utcnow().isoformat()),
        "last_completed": job.get("last_completed"),
        "last_triggered": job.get("last_triggered"),
        "is_due": bool(job.get("is_due", False)),
    }


def _ensure_timezone_aware_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=utcnow().tzinfo)
    return parsed


def _ensure_timezone_aware_iso(value: str) -> str:
    return _ensure_timezone_aware_datetime(value).isoformat()


def _compute_next_due(job: dict[str, Any]) -> datetime | None:
    trigger_type = job.get("trigger_type")

    if trigger_type == TRIGGER_TYPE_SCHEDULE:
        cron_expression = job.get("cron_expression")
        if not cron_expression:
            return None
        try:
            return croniter(cron_expression, utcnow()).get_next(ret_type=datetime)
        except (CroniterBadCronError, ValueError, TypeError) as err:
            _LOGGER.error("Error computing next due for %s: %s", job.get("name"), err)
            return None

    if trigger_type == TRIGGER_TYPE_FREQUENCY:
        days_interval = job.get("days_interval")
        if not days_interval or days_interval <= 0:
            return None
        if job.get("last_completed"):
            try:
                return _ensure_timezone_aware_datetime(job["last_completed"]) + timedelta(
                    days=days_interval
                )
            except (OverflowError, ValueError, TypeError) as err:
                _LOGGER.error("Error computing frequency due for %s: %s", job.get("name"), err)
                return None
        return _ensure_timezone_aware_datetime(job["created"])

    return None


def _is_due(job: dict[str, Any]) -> bool:
    if job.get("is_due"):
        return True

    trigger_type = job.get("trigger_type")
    if trigger_type == TRIGGER_TYPE_SCHEDULE:
        cron_expression = job.get("cron_expression")
        if not cron_expression:
            return False
        try:
            now = utcnow()
            last_occurrence = croniter(cron_expression, now).get_prev(ret_type=datetime)
            last_triggered = job.get("last_triggered")
            return not last_triggered or _ensure_timezone_aware_datetime(last_triggered) < last_occurrence
        except (CroniterBadCronError, ValueError, TypeError) as err:
            _LOGGER.error("Error checking schedule for %s: %s", job.get("name"), err)
            return False

    if trigger_type == TRIGGER_TYPE_FREQUENCY:
        days_interval = job.get("days_interval")
        if not days_interval or days_interval <= 0:
            return False
        last_completed = job.get("last_completed")
        if not last_completed:
            return True
        try:
            due_date = _ensure_timezone_aware_datetime(last_completed) + timedelta(days=days_interval)
            return utcnow() >= due_date
        except (OverflowError, ValueError, TypeError) as err:
            _LOGGER.error("Error checking frequency for %s: %s", job.get("name"), err)
            return False

    return False


async def _ensure_runtime(hass: HomeAssistant, entry_id: str) -> dict[str, Any]:
    data = _entry_data(hass, entry_id)
    if "jobs_store" not in data:
        data["jobs_store"] = Store(hass, STORAGE_VERSION, _jobs_storage_key(entry_id))
    if "jobs" not in data:
        jobs_data = await data["jobs_store"].async_load() or {"jobs": []}
        data["jobs"] = {
            job["id"]: _normalize_job(job) for job in jobs_data.get("jobs", []) if job.get("id")
        }
    data.setdefault("job_binary_entities", {})
    data.setdefault("job_sensor_entities", {})
    return data


async def _save_jobs(hass: HomeAssistant, entry_id: str) -> None:
    data = await _ensure_runtime(hass, entry_id)
    store = data["jobs_store"]
    await store.async_save({"jobs": list(data["jobs"].values())})


async def async_setup_binary_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors for jobs."""
    data = await _ensure_runtime(hass, config_entry.entry_id)
    data["job_binary_add_entities"] = async_add_entities

    entities = [
        JobDueBinarySensor(hass, config_entry.entry_id, job_id)
        for job_id in sorted(data["jobs"])
    ]
    if entities:
        async_add_entities(entities)
        for entity in entities:
            data["job_binary_entities"][entity.job_id] = entity


async def async_setup_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for jobs."""
    data = await _ensure_runtime(hass, config_entry.entry_id)
    data["job_sensor_add_entities"] = async_add_entities

    entities: list[SensorEntity] = []
    for job_id in sorted(data["jobs"]):
        entities.extend(_build_job_sensor_entities(hass, config_entry.entry_id, job_id))

    if entities:
        async_add_entities(entities)
        _store_job_sensor_entities(data, entities)


def _build_job_sensor_entities(
    hass: HomeAssistant,
    entry_id: str,
    job_id: str,
) -> list[SensorEntity]:
    return [
        JobTimestampSensor(hass, entry_id, job_id, ATTR_LAST_TRIGGERED, "Last Triggered"),
        JobTimestampSensor(hass, entry_id, job_id, ATTR_LAST_COMPLETED, "Last Completed"),
        JobTimestampSensor(hass, entry_id, job_id, ATTR_NEXT_DUE, "Next Due"),
        JobTimestampSensor(hass, entry_id, job_id, ATTR_CREATED, "Created"),
        JobNumericSensor(hass, entry_id, job_id, ATTR_PRIORITY, "Priority"),
    ]


def _store_job_sensor_entities(data: dict[str, Any], entities: list[SensorEntity]) -> None:
    by_job = data.setdefault("job_sensor_entities", {})
    for entity in entities:
        by_job.setdefault(entity.job_id, []).append(entity)


def _find_job_by_target(
    hass: HomeAssistant, entity_id: str | None, job_id: str | None
) -> tuple[str, dict[str, Any], dict[str, Any]] | None:
    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        jobs = data.get("jobs", {})
        if job_id and job_id in jobs:
            return entry_id, data, jobs[job_id]
        if entity_id:
            binary_entity = data.get("job_binary_entities", {}).get(_job_id_from_entity_id(entity_id))
            if binary_entity and binary_entity.job_id in jobs:
                return entry_id, data, jobs[binary_entity.job_id]
    return None


def _job_id_from_entity_id(entity_id: str) -> str | None:
    prefix = f"binary_sensor.{PREFIX_JOBS}_"
    if not entity_id.startswith(prefix):
        return None
    return entity_id[len(prefix) :]


async def async_setup_jobs_services(hass: HomeAssistant) -> None:
    """Register Raven Castle Jobs services."""

    async def _trigger_job(call: ServiceCall) -> None:
        result = _find_job_by_target(hass, call.data.get("entity_id"), call.data.get("job_id"))
        if result is None:
            return
        entry_id, _, job = result
        job["is_due"] = True
        job["last_triggered"] = utcnow().isoformat()
        await _save_jobs(hass, entry_id)
        async_dispatcher_send(hass, f"{JOBS_SIGNAL_UPDATE}_{entry_id}_{job['id']}")

    async def _complete_job(call: ServiceCall) -> None:
        result = _find_job_by_target(hass, call.data.get("entity_id"), call.data.get("job_id"))
        if result is None:
            return
        entry_id, _, job = result
        job["is_due"] = False
        now = utcnow().isoformat()
        job["last_completed"] = now
        job["last_triggered"] = job.get("last_triggered") or now
        await _save_jobs(hass, entry_id)
        async_dispatcher_send(hass, f"{JOBS_SIGNAL_UPDATE}_{entry_id}_{job['id']}")

    target_schema = vol.Schema(
        {
            vol.Optional("entity_id"): cv.entity_id,
            vol.Optional("job_id"): cv.string,
        }
    )

    if not hass.services.has_service(DOMAIN, SERVICE_TRIGGER_JOB):
        hass.services.async_register(DOMAIN, SERVICE_TRIGGER_JOB, _trigger_job, schema=target_schema)

    if not hass.services.has_service(DOMAIN, SERVICE_COMPLETE_JOB):
        hass.services.async_register(DOMAIN, SERVICE_COMPLETE_JOB, _complete_job, schema=target_schema)


async def async_sync_jobs_from_storage(hass: HomeAssistant, entry_id: str) -> None:
    """Synchronize runtime entities with stored jobs."""
    data = await _ensure_runtime(hass, entry_id)
    jobs_data = await data["jobs_store"].async_load() or {"jobs": []}
    new_jobs = {
        job["id"]: _normalize_job(job) for job in jobs_data.get("jobs", []) if job.get("id")
    }

    existing_ids = set(data["jobs"])
    new_ids = set(new_jobs)

    for removed_job_id in existing_ids - new_ids:
        binary_entity = data.get("job_binary_entities", {}).pop(removed_job_id, None)
        if binary_entity is not None:
            await binary_entity.async_remove()
        for entity in data.get("job_sensor_entities", {}).pop(removed_job_id, []):
            await entity.async_remove()

    for job_id in existing_ids & new_ids:
        data["jobs"][job_id].update(new_jobs[job_id])
        async_dispatcher_send(hass, f"{JOBS_SIGNAL_UPDATE}_{entry_id}_{job_id}")

    data["jobs"].update({job_id: new_jobs[job_id] for job_id in new_ids - existing_ids})

    added_job_ids = sorted(new_ids - existing_ids)
    binary_add = data.get("job_binary_add_entities")
    if binary_add and added_job_ids:
        binary_entities = [
            JobDueBinarySensor(hass, entry_id, job_id)
            for job_id in added_job_ids
        ]
        binary_add(binary_entities)
        for entity in binary_entities:
            data["job_binary_entities"][entity.job_id] = entity

    sensor_add = data.get("job_sensor_add_entities")
    if sensor_add and added_job_ids:
        sensor_entities: list[SensorEntity] = []
        for job_id in added_job_ids:
            sensor_entities.extend(_build_job_sensor_entities(hass, entry_id, job_id))
        sensor_add(sensor_entities)
        _store_job_sensor_entities(data, sensor_entities)


class JobEntityBase:
    """Shared helpers for job entities."""

    def __init__(self, hass: HomeAssistant, entry_id: str, job_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.job_id = job_id

    @property
    def _job(self) -> dict[str, Any] | None:
        return _entry_data(self.hass, self.entry_id).get("jobs", {}).get(self.job_id)

    @property
    def _device_info(self) -> DeviceInfo:
        job = self._job or {}
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry_id}_{self.job_id}")},
            name=job.get("name") or f"RC Job {self.job_id}",
            manufacturer="Raven Castle",
            model="Raven Castle Job",
        )

    @property
    def device_info(self) -> DeviceInfo:
        return self._device_info

    async def _subscribe_updates(self) -> Callable[[], None]:
        @callback
        def _handle_update() -> None:
            self.async_write_ha_state()

        return async_dispatcher_connect(
            self.hass,
            f"{JOBS_SIGNAL_UPDATE}_{self.entry_id}_{self.job_id}",
            _handle_update,
        )


class JobDueBinarySensor(JobEntityBase, BinarySensorEntity):
    """Primary due/not-due entity for a job device."""

    def __init__(self, hass: HomeAssistant, entry_id: str, job_id: str) -> None:
        super().__init__(hass, entry_id, job_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{job_id}_due"
        self.entity_id = f"binary_sensor.{PREFIX_JOBS}_{job_id}"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(await self._subscribe_updates())

    @property
    def available(self) -> bool:
        return self._job is not None

    @property
    def name(self) -> str:
        job = self._job or {}
        return job.get("name") or f"RC Job {self.job_id}"

    @property
    def is_on(self) -> bool:
        job = self._job
        if not job:
            return False
        computed_due = _is_due(job)
        if computed_due and not job.get("is_due"):
            job["is_due"] = True
            job["last_triggered"] = job.get("last_triggered") or utcnow().isoformat()
            self.hass.async_create_task(_save_jobs(self.hass, self.entry_id))
            async_dispatcher_send(
                self.hass,
                f"{JOBS_SIGNAL_UPDATE}_{self.entry_id}_{self.job_id}",
            )
        return bool(job.get("is_due"))

    @property
    def icon(self) -> str:
        return "mdi:clipboard-check" if self.is_on else "mdi:clipboard-text-clock"

    @property
    def device_class(self) -> str:
        return "problem"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        job = self._job or {}
        return {
            ATTR_JOB_ID: self.job_id,
            ATTR_ENTITY_ROLE: "primary",
            ATTR_TRIGGER_TYPE: job.get("trigger_type"),
            ATTR_CRON_EXPRESSION: job.get("cron_expression"),
            ATTR_DAYS_INTERVAL: job.get("days_interval"),
            ATTR_LAST_COMPLETED: job.get("last_completed"),
            ATTR_LAST_TRIGGERED: job.get("last_triggered"),
            ATTR_CREATED: job.get("created"),
            ATTR_IMAGE: job.get("image", ""),
            ATTR_PRIORITY: int(job.get("priority", 0)),
            ATTR_NEXT_DUE: (_compute_next_due(job).isoformat() if _compute_next_due(job) else None),
        }


class JobTimestampSensor(JobEntityBase, SensorEntity):
    """Timestamp sensors for a job device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        job_id: str,
        field_name: str,
        label: str,
    ) -> None:
        super().__init__(hass, entry_id, job_id)
        self._field_name = field_name
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{job_id}_{field_name}"
        self.entity_id = f"sensor.{PREFIX_JOBS}_{job_id}_{field_name}"
        self._attr_name = label
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(await self._subscribe_updates())

    @property
    def available(self) -> bool:
        return self._job is not None

    @property
    def native_value(self) -> datetime | None:
        job = self._job
        if not job:
            return None
        if self._field_name == ATTR_NEXT_DUE:
            return _compute_next_due(job)
        value = job.get(self._field_name)
        return _ensure_timezone_aware_datetime(value) if value else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_JOB_ID: self.job_id, ATTR_ENTITY_ROLE: self._field_name}


class JobNumericSensor(JobEntityBase, SensorEntity):
    """Numeric sensors for a job device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        job_id: str,
        field_name: str,
        label: str,
    ) -> None:
        super().__init__(hass, entry_id, job_id)
        self._field_name = field_name
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{job_id}_{field_name}"
        self.entity_id = f"sensor.{PREFIX_JOBS}_{job_id}_{field_name}"
        self._attr_name = label

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(await self._subscribe_updates())

    @property
    def available(self) -> bool:
        return self._job is not None

    @property
    def native_value(self) -> int | None:
        job = self._job
        if not job:
            return None
        value = job.get(self._field_name)
        return int(value) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_JOB_ID: self.job_id, ATTR_ENTITY_ROLE: self._field_name}