"""Config flow for Raven Castle Jobs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import utcnow

from .const import DOMAIN, STORAGE_VERSION, TRIGGER_TYPE_FREQUENCY, TRIGGER_TYPE_SCHEDULE
from .entities import _jobs_storage_key, async_sync_jobs_from_storage


class RavenCastleJobsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Raven Castle Jobs."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="Raven Castle Jobs", data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return RavenCastleJobsOptionsFlow(config_entry)


class RavenCastleJobsOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Raven Castle Jobs."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry
        self._editing_job_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage jobs."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["create_job", "list_jobs"],
        )

    async def async_step_create_job(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle job creation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            trigger_type = user_input.get("trigger_type")
            if not user_input.get("name"):
                errors["name"] = "name_required"
            elif trigger_type == TRIGGER_TYPE_SCHEDULE and not user_input.get(
                "cron_expression"
            ):
                errors["cron_expression"] = "cron_required"
            elif trigger_type == TRIGGER_TYPE_FREQUENCY and (
                not user_input.get("days_interval")
                or user_input.get("days_interval") <= 0
            ):
                errors["days_interval"] = "days_required"

            if not errors:
                store = Store(
                    self.hass,
                    STORAGE_VERSION,
                    _jobs_storage_key(self._config_entry.entry_id),
                )
                jobs_data = await store.async_load() or {"jobs": []}
                jobs_data["jobs"].append(
                    {
                        "id": str(uuid.uuid4())[:8],
                        "name": user_input["name"],
                        "trigger_type": trigger_type,
                        "cron_expression": user_input.get("cron_expression"),
                        "days_interval": user_input.get("days_interval"),
                        "image": user_input.get("image", ""),
                        "priority": user_input.get("priority", 0),
                        "created": datetime.isoformat(utcnow()),
                    }
                )
                await store.async_save(jobs_data)
                await async_sync_jobs_from_storage(self.hass, self._config_entry.entry_id)
                return self.async_abort(reason="job_created")

        return self.async_show_form(
            step_id="create_job",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): cv.string,
                    vol.Required(
                        "trigger_type", default=TRIGGER_TYPE_SCHEDULE
                    ): vol.In(
                        {
                            TRIGGER_TYPE_SCHEDULE: "Schedule (Cron)",
                            TRIGGER_TYPE_FREQUENCY: "Frequency (Days)",
                        }
                    ),
                    vol.Optional("cron_expression", default="0 0 * * *"): cv.string,
                    vol.Optional("days_interval", default=7): cv.positive_int,
                    vol.Optional("image", default=""): cv.string,
                    vol.Optional("priority", default=0): cv.positive_int,
                }
            ),
            errors=errors,
        )

    async def async_step_list_jobs(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show jobs to edit."""
        store = Store(
            self.hass,
            STORAGE_VERSION,
            _jobs_storage_key(self._config_entry.entry_id),
        )
        jobs_data = await store.async_load() or {"jobs": []}
        jobs = jobs_data.get("jobs", [])

        if not jobs:
            return self.async_abort(reason="no_jobs")

        choices = {job["id"]: job["name"] for job in jobs}
        if user_input is not None:
            return await self.async_step_edit_job(job_id=user_input.get("job_id"))

        return self.async_show_form(
            step_id="list_jobs",
            data_schema=vol.Schema({vol.Required("job_id"): vol.In(choices)}),
        )

    async def async_step_edit_job(
        self,
        user_input: dict[str, Any] | None = None,
        job_id: str | None = None,
    ) -> FlowResult:
        """Handle job editing and deletion."""
        if job_id:
            self._editing_job_id = job_id
        else:
            job_id = self._editing_job_id

        if not job_id:
            return self.async_abort(reason="job_not_found")

        store = Store(
            self.hass,
            STORAGE_VERSION,
            _jobs_storage_key(self._config_entry.entry_id),
        )
        jobs_data = await store.async_load() or {"jobs": []}
        jobs = jobs_data.get("jobs", [])
        job = next((item for item in jobs if item["id"] == job_id), None)
        if not job:
            return self.async_abort(reason="job_not_found")

        errors: dict[str, str] = {}
        if user_input is not None:
            action = user_input.get("action", "update")
            if action == "delete":
                jobs_data["jobs"] = [item for item in jobs if item["id"] != job_id]
                await store.async_save(jobs_data)
                await async_sync_jobs_from_storage(self.hass, self._config_entry.entry_id)
                return self.async_abort(reason="job_deleted")

            trigger_type = user_input.get("trigger_type")
            if not user_input.get("name"):
                errors["name"] = "name_required"
            elif trigger_type == TRIGGER_TYPE_SCHEDULE and not user_input.get(
                "cron_expression"
            ):
                errors["cron_expression"] = "cron_required"
            elif trigger_type == TRIGGER_TYPE_FREQUENCY and (
                not user_input.get("days_interval")
                or user_input.get("days_interval") <= 0
            ):
                errors["days_interval"] = "days_required"

            if not errors:
                job.update(
                    {
                        "name": user_input["name"],
                        "trigger_type": trigger_type,
                        "cron_expression": user_input.get("cron_expression"),
                        "days_interval": user_input.get("days_interval"),
                        "image": user_input.get("image", ""),
                        "priority": user_input.get("priority", 0),
                    }
                )
                await store.async_save(jobs_data)
                await async_sync_jobs_from_storage(self.hass, self._config_entry.entry_id)
                return self.async_abort(reason="job_updated")

        return self.async_show_form(
            step_id="edit_job",
            data_schema=vol.Schema(
                {
                    vol.Required("name", default=job.get("name", "")): cv.string,
                    vol.Required(
                        "trigger_type",
                        default=job.get("trigger_type", TRIGGER_TYPE_SCHEDULE),
                    ): vol.In(
                        {
                            TRIGGER_TYPE_SCHEDULE: "Schedule (Cron)",
                            TRIGGER_TYPE_FREQUENCY: "Frequency (Days)",
                        }
                    ),
                    vol.Optional(
                        "cron_expression",
                        default=job.get("cron_expression", "0 0 * * *"),
                    ): cv.string,
                    vol.Optional(
                        "days_interval", default=job.get("days_interval", 7)
                    ): cv.positive_int,
                    vol.Optional("image", default=job.get("image", "")): cv.string,
                    vol.Optional("priority", default=job.get("priority", 0)): cv.positive_int,
                    vol.Required("action", default="update"): vol.In(
                        {"update": "Save Changes", "delete": "Delete Job"}
                    ),
                }
            ),
            errors=errors,
        )