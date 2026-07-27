"""Entity model for Raven House Jobs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any
import uuid

import voluptuous as vol
from croniter import CroniterBadCronError, croniter
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.number import NumberEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.text import TextEntity
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
    SERVICE_ADD_JOB,
    SERVICE_COMPLETE_JOB,
    SERVICE_DISMISS_JOB,
    SERVICE_RENAME_JOB,
    SERVICE_TRIGGER_JOB,
    STORAGE_VERSION,
    TRIGGER_TYPE_FREQUENCY,
    TRIGGER_TYPE_SCHEDULE,
)
from .features import entry_id_supports_jobs

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
        "manual_due": bool(job.get("manual_due", job.get("is_due", False))),
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
    if job.get("manual_due"):
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
        reference_timestamp = job.get("last_completed") or job.get("last_triggered")
        if not reference_timestamp:
            return True
        try:
            due_date = _ensure_timezone_aware_datetime(reference_timestamp) + timedelta(
                days=days_interval
            )
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
    data.setdefault("job_button_entities", {})
    data.setdefault("job_text_entities", {})
    data.setdefault("job_number_entities", {})
    data.setdefault("job_select_entities", {})
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


async def async_setup_buttons(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons for jobs."""
    data = await _ensure_runtime(hass, config_entry.entry_id)
    data["job_button_add_entities"] = async_add_entities

    entities: list[ButtonEntity] = []
    for job_id in sorted(data["jobs"]):
        entities.extend(_build_job_button_entities(hass, config_entry.entry_id, job_id))
    if entities:
        async_add_entities(entities)
        _store_job_button_entities(data, entities)


async def async_setup_texts(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up text entities for jobs."""
    data = await _ensure_runtime(hass, config_entry.entry_id)
    data["job_text_add_entities"] = async_add_entities

    entities: list[TextEntity] = []
    for job_id in sorted(data["jobs"]):
        entities.extend(_build_job_text_entities(hass, config_entry.entry_id, job_id))
    if entities:
        async_add_entities(entities)
        _store_job_text_entities(data, entities)


async def async_setup_numbers(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities for jobs."""
    data = await _ensure_runtime(hass, config_entry.entry_id)
    data["job_number_add_entities"] = async_add_entities

    entities: list[NumberEntity] = []
    for job_id in sorted(data["jobs"]):
        entities.extend(_build_job_number_entities(hass, config_entry.entry_id, job_id))
    if entities:
        async_add_entities(entities)
        _store_job_number_entities(data, entities)


async def async_setup_selects(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities for jobs."""
    data = await _ensure_runtime(hass, config_entry.entry_id)
    data["job_select_add_entities"] = async_add_entities

    entities = [
        JobTriggerTypeSelect(hass, config_entry.entry_id, job_id)
        for job_id in sorted(data["jobs"])
    ]
    if entities:
        async_add_entities(entities)
        for entity in entities:
            data["job_select_entities"][entity.job_id] = entity


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


def _build_job_button_entities(
    hass: HomeAssistant,
    entry_id: str,
    job_id: str,
) -> list[ButtonEntity]:
    return [
        JobTriggerButton(hass, entry_id, job_id),
        JobCompleteButton(hass, entry_id, job_id),
    ]


def _store_job_button_entities(data: dict[str, Any], entities: list[ButtonEntity]) -> None:
    by_job = data.setdefault("job_button_entities", {})
    for entity in entities:
        by_job.setdefault(entity.job_id, []).append(entity)


def _build_job_text_entities(
    hass: HomeAssistant,
    entry_id: str,
    job_id: str,
) -> list[TextEntity]:
    return [
        JobNameText(hass, entry_id, job_id),
        JobCronExpressionText(hass, entry_id, job_id),
        JobImageText(hass, entry_id, job_id),
    ]


def _store_job_text_entities(data: dict[str, Any], entities: list[TextEntity]) -> None:
    by_job = data.setdefault("job_text_entities", {})
    for entity in entities:
        by_job.setdefault(entity.job_id, []).append(entity)


def _build_job_number_entities(
    hass: HomeAssistant,
    entry_id: str,
    job_id: str,
) -> list[NumberEntity]:
    return [
        JobPriorityNumber(hass, entry_id, job_id),
        JobDaysIntervalNumber(hass, entry_id, job_id),
    ]


def _store_job_number_entities(data: dict[str, Any], entities: list[NumberEntity]) -> None:
    by_job = data.setdefault("job_number_entities", {})
    for entity in entities:
        by_job.setdefault(entity.job_id, []).append(entity)


def _find_job_by_target(
    hass: HomeAssistant, entity_id: str | None, job_id: str | None
) -> tuple[str, dict[str, Any], dict[str, Any]] | None:
    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        if not entry_id_supports_jobs(hass, entry_id):
            continue
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
    """Register Raven House Jobs services."""

    async def _trigger_job(call: ServiceCall) -> None:
        result = _find_job_by_target(hass, call.data.get("entity_id"), call.data.get("job_id"))
        if result is None:
            return
        entry_id, _, job = result
        job["manual_due"] = True
        job["last_triggered"] = utcnow().isoformat()
        await _save_jobs(hass, entry_id)
        async_dispatcher_send(hass, f"{JOBS_SIGNAL_UPDATE}_{entry_id}_{job['id']}")

    async def _complete_job(call: ServiceCall) -> None:
        result = _find_job_by_target(hass, call.data.get("entity_id"), call.data.get("job_id"))
        if result is None:
            return
        entry_id, _, job = result
        now = utcnow().isoformat()
        job["manual_due"] = False
        job["last_completed"] = now
        job["last_triggered"] = now
        await _save_jobs(hass, entry_id)
        async_dispatcher_send(hass, f"{JOBS_SIGNAL_UPDATE}_{entry_id}_{job['id']}")

    async def _dismiss_job(call: ServiceCall) -> None:
        result = _find_job_by_target(hass, call.data.get("entity_id"), call.data.get("job_id"))
        if result is None:
            return
        entry_id, _, job = result
        job["manual_due"] = False
        job["last_triggered"] = utcnow().isoformat()
        await _save_jobs(hass, entry_id)
        async_dispatcher_send(hass, f"{JOBS_SIGNAL_UPDATE}_{entry_id}_{job['id']}")

    async def _rename_job(call: ServiceCall) -> None:
        result = _find_job_by_target(hass, call.data.get("entity_id"), call.data.get("job_id"))
        if result is None:
            return
        entry_id, _, job = result
        name = str(call.data.get("name", "")).strip()
        if not name:
            return
        job["name"] = name
        await _save_jobs(hass, entry_id)
        async_dispatcher_send(hass, f"{JOBS_SIGNAL_UPDATE}_{entry_id}_{job['id']}")

    async def _add_job(call: ServiceCall) -> None:
        trigger_type = call.data.get("trigger_type", TRIGGER_TYPE_SCHEDULE)
        name = str(call.data.get("name", "")).strip()
        if not name:
            return

        for entry_id in hass.data.get(DOMAIN, {}):
            if not entry_id_supports_jobs(hass, entry_id):
                continue
            data = await _ensure_runtime(hass, entry_id)
            job_id = str(uuid.uuid4())[:8]
            data["jobs"][job_id] = _normalize_job(
                {
                    "id": job_id,
                    "name": name,
                    "trigger_type": trigger_type,
                    "cron_expression": call.data.get("cron_expression"),
                    "days_interval": call.data.get("days_interval"),
                    "image": call.data.get("image", ""),
                    "priority": int(call.data.get("priority", 0)),
                    "created": utcnow().isoformat(),
                    "manual_due": False,
                }
            )
            await _save_jobs(hass, entry_id)
            await async_sync_jobs_from_storage(hass, entry_id)
            return

    target_schema = vol.Schema(
        {
            vol.Optional("entity_id"): cv.entity_id,
            vol.Optional("job_id"): cv.string,
        }
    )
    add_job_schema = vol.Schema(
        {
            vol.Required("name"): cv.string,
            vol.Optional("trigger_type", default=TRIGGER_TYPE_SCHEDULE): vol.In(
                [TRIGGER_TYPE_SCHEDULE, TRIGGER_TYPE_FREQUENCY]
            ),
            vol.Optional("cron_expression"): cv.string,
            vol.Optional("days_interval"): cv.positive_int,
            vol.Optional("image", default=""): cv.string,
            vol.Optional("priority", default=0): vol.Coerce(int),
        }
    )
    rename_schema = vol.Schema(
        {
            vol.Optional("entity_id"): cv.entity_id,
            vol.Optional("job_id"): cv.string,
            vol.Required("name"): cv.string,
        }
    )

    if not hass.services.has_service(DOMAIN, SERVICE_TRIGGER_JOB):
        hass.services.async_register(DOMAIN, SERVICE_TRIGGER_JOB, _trigger_job, schema=target_schema)

    if not hass.services.has_service(DOMAIN, SERVICE_COMPLETE_JOB):
        hass.services.async_register(DOMAIN, SERVICE_COMPLETE_JOB, _complete_job, schema=target_schema)

    if not hass.services.has_service(DOMAIN, SERVICE_DISMISS_JOB):
        hass.services.async_register(DOMAIN, SERVICE_DISMISS_JOB, _dismiss_job, schema=target_schema)

    if not hass.services.has_service(DOMAIN, SERVICE_RENAME_JOB):
        hass.services.async_register(DOMAIN, SERVICE_RENAME_JOB, _rename_job, schema=rename_schema)

    if not hass.services.has_service(DOMAIN, SERVICE_ADD_JOB):
        hass.services.async_register(DOMAIN, SERVICE_ADD_JOB, _add_job, schema=add_job_schema)


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
        for entity in data.get("job_button_entities", {}).pop(removed_job_id, []):
            await entity.async_remove()
        for entity in data.get("job_text_entities", {}).pop(removed_job_id, []):
            await entity.async_remove()
        for entity in data.get("job_number_entities", {}).pop(removed_job_id, []):
            await entity.async_remove()
        select_entity = data.get("job_select_entities", {}).pop(removed_job_id, None)
        if select_entity is not None:
            await select_entity.async_remove()

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

    button_add = data.get("job_button_add_entities")
    if button_add and added_job_ids:
        button_entities: list[ButtonEntity] = []
        for job_id in added_job_ids:
            button_entities.extend(_build_job_button_entities(hass, entry_id, job_id))
        button_add(button_entities)
        _store_job_button_entities(data, button_entities)

    text_add = data.get("job_text_add_entities")
    if text_add and added_job_ids:
        text_entities: list[TextEntity] = []
        for job_id in added_job_ids:
            text_entities.extend(_build_job_text_entities(hass, entry_id, job_id))
        text_add(text_entities)
        _store_job_text_entities(data, text_entities)

    number_add = data.get("job_number_add_entities")
    if number_add and added_job_ids:
        number_entities: list[NumberEntity] = []
        for job_id in added_job_ids:
            number_entities.extend(_build_job_number_entities(hass, entry_id, job_id))
        number_add(number_entities)
        _store_job_number_entities(data, number_entities)

    select_add = data.get("job_select_add_entities")
    if select_add and added_job_ids:
        select_entities = [JobTriggerTypeSelect(hass, entry_id, job_id) for job_id in added_job_ids]
        select_add(select_entities)
        for entity in select_entities:
            data["job_select_entities"][entity.job_id] = entity


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
            name=job.get("name") or f"RH Job {self.job_id}",
            manufacturer="Raven House",
            model="Raven House Job",
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
        return job.get("name") or f"RH Job {self.job_id}"

    @property
    def is_on(self) -> bool:
        job = self._job
        if not job:
            return False
        return _is_due(job)

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


class JobActionButton(JobEntityBase, ButtonEntity):
    """Base button for job actions."""

    def __init__(self, hass: HomeAssistant, entry_id: str, job_id: str) -> None:
        super().__init__(hass, entry_id, job_id)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(await self._subscribe_updates())

    @property
    def available(self) -> bool:
        return self._job is not None


class JobTriggerButton(JobActionButton):
    """Button to trigger a job manually."""

    def __init__(self, hass: HomeAssistant, entry_id: str, job_id: str) -> None:
        super().__init__(hass, entry_id, job_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{job_id}_trigger"
        self.entity_id = f"button.{PREFIX_JOBS}_{job_id}_trigger"
        self._attr_name = "Trigger Job"

    async def async_press(self) -> None:
        job = self._job
        if not job:
            return
        job["manual_due"] = True
        job["last_triggered"] = utcnow().isoformat()
        await _save_jobs(self.hass, self.entry_id)
        async_dispatcher_send(self.hass, f"{JOBS_SIGNAL_UPDATE}_{self.entry_id}_{self.job_id}")


class JobCompleteButton(JobActionButton):
    """Button to mark a job complete."""

    def __init__(self, hass: HomeAssistant, entry_id: str, job_id: str) -> None:
        super().__init__(hass, entry_id, job_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{job_id}_complete"
        self.entity_id = f"button.{PREFIX_JOBS}_{job_id}_complete"
        self._attr_name = "Complete Job"

    async def async_press(self) -> None:
        job = self._job
        if not job:
            return
        job["manual_due"] = False
        now = utcnow().isoformat()
        job["last_triggered"] = now
        job["last_completed"] = now
        await _save_jobs(self.hass, self.entry_id)
        async_dispatcher_send(self.hass, f"{JOBS_SIGNAL_UPDATE}_{self.entry_id}_{self.job_id}")


class JobNameText(JobEntityBase, TextEntity):
    """Text entity to rename a job from the device page."""

    def __init__(self, hass: HomeAssistant, entry_id: str, job_id: str) -> None:
        super().__init__(hass, entry_id, job_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{job_id}_name"
        self.entity_id = f"text.{PREFIX_JOBS}_{job_id}_name"
        self._attr_name = "Name"
        self._attr_native_min = 1
        self._attr_native_max = 120

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(await self._subscribe_updates())

    @property
    def available(self) -> bool:
        return self._job is not None

    @property
    def native_value(self) -> str:
        job = self._job or {}
        return job.get("name", "")

    async def async_set_value(self, value: str) -> None:
        name = value.strip()
        if not name:
            return
        job = self._job
        if not job:
            return
        job["name"] = name
        await _save_jobs(self.hass, self.entry_id)
        async_dispatcher_send(self.hass, f"{JOBS_SIGNAL_UPDATE}_{self.entry_id}_{self.job_id}")


class JobCronExpressionText(JobEntityBase, TextEntity):
    """Text entity for cron expression management."""

    def __init__(self, hass: HomeAssistant, entry_id: str, job_id: str) -> None:
        super().__init__(hass, entry_id, job_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{job_id}_cron_expression"
        self.entity_id = f"text.{PREFIX_JOBS}_{job_id}_cron_expression"
        self._attr_name = "Cron Expression"
        self._attr_native_min = 0
        self._attr_native_max = 120

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(await self._subscribe_updates())

    @property
    def available(self) -> bool:
        return self._job is not None

    @property
    def native_value(self) -> str:
        job = self._job or {}
        return job.get("cron_expression") or ""

    async def async_set_value(self, value: str) -> None:
        job = self._job
        if not job:
            return
        job["cron_expression"] = value.strip()
        await _save_jobs(self.hass, self.entry_id)
        async_dispatcher_send(self.hass, f"{JOBS_SIGNAL_UPDATE}_{self.entry_id}_{self.job_id}")


class JobImageText(JobEntityBase, TextEntity):
    """Text entity for image URL/path management."""

    def __init__(self, hass: HomeAssistant, entry_id: str, job_id: str) -> None:
        super().__init__(hass, entry_id, job_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{job_id}_image"
        self.entity_id = f"text.{PREFIX_JOBS}_{job_id}_image"
        self._attr_name = "Image"
        self._attr_native_min = 0
        self._attr_native_max = 512

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(await self._subscribe_updates())

    @property
    def available(self) -> bool:
        return self._job is not None

    @property
    def native_value(self) -> str:
        job = self._job or {}
        return job.get("image") or ""

    async def async_set_value(self, value: str) -> None:
        job = self._job
        if not job:
            return
        job["image"] = value.strip()
        await _save_jobs(self.hass, self.entry_id)
        async_dispatcher_send(self.hass, f"{JOBS_SIGNAL_UPDATE}_{self.entry_id}_{self.job_id}")


class JobPriorityNumber(JobEntityBase, NumberEntity):
    """Number entity for job priority."""

    def __init__(self, hass: HomeAssistant, entry_id: str, job_id: str) -> None:
        super().__init__(hass, entry_id, job_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{job_id}_priority_control"
        self.entity_id = f"number.{PREFIX_JOBS}_{job_id}_priority"
        self._attr_name = "Priority"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 1000
        self._attr_native_step = 1
        self._attr_mode = "box"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(await self._subscribe_updates())

    @property
    def available(self) -> bool:
        return self._job is not None

    @property
    def native_value(self) -> float:
        job = self._job or {}
        return float(int(job.get("priority", 0)))

    async def async_set_native_value(self, value: float) -> None:
        job = self._job
        if not job:
            return
        job["priority"] = int(value)
        await _save_jobs(self.hass, self.entry_id)
        async_dispatcher_send(self.hass, f"{JOBS_SIGNAL_UPDATE}_{self.entry_id}_{self.job_id}")


class JobDaysIntervalNumber(JobEntityBase, NumberEntity):
    """Number entity for frequency interval in days."""

    def __init__(self, hass: HomeAssistant, entry_id: str, job_id: str) -> None:
        super().__init__(hass, entry_id, job_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{job_id}_days_interval"
        self.entity_id = f"number.{PREFIX_JOBS}_{job_id}_days_interval"
        self._attr_name = "Days Interval"
        self._attr_native_min_value = 1
        self._attr_native_max_value = 3650
        self._attr_native_step = 1
        self._attr_mode = "box"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(await self._subscribe_updates())

    @property
    def available(self) -> bool:
        return self._job is not None

    @property
    def native_value(self) -> float:
        job = self._job or {}
        return float(int(job.get("days_interval", 7) or 7))

    async def async_set_native_value(self, value: float) -> None:
        job = self._job
        if not job:
            return
        job["days_interval"] = int(value)
        await _save_jobs(self.hass, self.entry_id)
        async_dispatcher_send(self.hass, f"{JOBS_SIGNAL_UPDATE}_{self.entry_id}_{self.job_id}")


class JobTriggerTypeSelect(JobEntityBase, SelectEntity):
    """Select entity for choosing trigger type."""

    _attr_options = [TRIGGER_TYPE_SCHEDULE, TRIGGER_TYPE_FREQUENCY]

    def __init__(self, hass: HomeAssistant, entry_id: str, job_id: str) -> None:
        super().__init__(hass, entry_id, job_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{job_id}_trigger_type"
        self.entity_id = f"select.{PREFIX_JOBS}_{job_id}_trigger_type"
        self._attr_name = "Trigger Type"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(await self._subscribe_updates())

    @property
    def available(self) -> bool:
        return self._job is not None

    @property
    def current_option(self) -> str | None:
        job = self._job or {}
        trigger_type = job.get("trigger_type", TRIGGER_TYPE_SCHEDULE)
        if trigger_type in self._attr_options:
            return trigger_type
        return TRIGGER_TYPE_SCHEDULE

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            return
        job = self._job
        if not job:
            return
        job["trigger_type"] = option
        if option == TRIGGER_TYPE_SCHEDULE and not job.get("cron_expression"):
            job["cron_expression"] = "0 0 * * *"
        if option == TRIGGER_TYPE_FREQUENCY and not job.get("days_interval"):
            job["days_interval"] = 7
        await _save_jobs(self.hass, self.entry_id)
        async_dispatcher_send(self.hass, f"{JOBS_SIGNAL_UPDATE}_{self.entry_id}_{self.job_id}")
