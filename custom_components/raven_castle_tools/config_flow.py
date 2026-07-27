"""Config flow for Raven Castle Tools."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional
import uuid

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.util.dt import utcnow

from .const import (
    DOMAIN,
    STORAGE_VERSION,
    TRIGGER_TYPE_FREQUENCY,
    TRIGGER_TYPE_SCHEDULE,
)
from .quiz_config_flow import QuizOptionsFlowMixin

_LOGGER = logging.getLogger(__name__)


class RavenCastleToolsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Raven Castle Tools."""

    VERSION = 2

    async def async_step_user(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Raven Castle Tools", data={})

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return RavenCastleToolsOptionsFlow(config_entry)


class RavenCastleToolsOptionsFlow(config_entries.OptionsFlow, QuizOptionsFlowMixin):
    """Handle options for Raven Castle Tools."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow state."""
        self._config_entry = config_entry
        self._editing_job_id: str | None = None

    async def async_step_init(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Manage integration options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["manage_jobs", "manage_quiz"],
        )

    async def async_step_manage_jobs(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Show menu to create or edit jobs."""
        return self.async_show_menu(
            step_id="manage_jobs",
            menu_options=["create_job", "list_jobs"],
        )

    async def async_step_create_job(
        self, user_input: Optional[dict[str, Any]] = None
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
                store = self.hass.helpers.storage.Store(
                    self.hass,
                    STORAGE_VERSION,
                    f"{DOMAIN}.jobs_{self._config_entry.entry_id}",
                )
                jobs_data = await store.async_load() or {"jobs": []}
                jobs_data["jobs"].append(
                    {
                        "id": str(uuid.uuid4())[:8],
                        "name": user_input["name"],
                        "trigger_type": trigger_type,
                        "cron_expression": user_input.get("cron_expression"),
                        "days_interval": user_input.get("days_interval"),
                        "image": user_input.get("image"),
                        "priority": user_input.get("priority", 0),
                        "created": datetime.isoformat(utcnow()),
                    }
                )
                await store.async_save(jobs_data)
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
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Show list of jobs to edit/delete."""
        store = self.hass.helpers.storage.Store(
            self.hass,
            STORAGE_VERSION,
            f"{DOMAIN}.jobs_{self._config_entry.entry_id}",
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
        user_input: Optional[dict[str, Any]] = None,
        job_id: Optional[str] = None,
    ) -> FlowResult:
        """Handle job editing/deletion."""
        if job_id:
            self._editing_job_id = job_id
        else:
            job_id = self._editing_job_id

        if not job_id:
            return self.async_abort(reason="job_not_found")

        store = self.hass.helpers.storage.Store(
            self.hass,
            STORAGE_VERSION,
            f"{DOMAIN}.jobs_{self._config_entry.entry_id}",
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
                        "cron_expression", default=job.get("cron_expression", "0 0 * * *")
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
