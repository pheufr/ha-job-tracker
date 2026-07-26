"""Config flow for Raven Castle."""
import logging
from typing import Any, Dict, Optional
import uuid

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, TRIGGER_TYPE_SCHEDULE, TRIGGER_TYPE_FREQUENCY

_LOGGER = logging.getLogger(__name__)


class RavenCastleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Raven Castle."""

    VERSION = 2

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Raven Castle", data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return RavenCastleOptionsFlow()


class RavenCastleOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Raven Castle."""

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "manage_jobs",
            ],
        )

    async def async_step_manage_jobs(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Show menu to create or edit jobs."""
        return self.async_show_menu(
            step_id="manage_jobs",
            menu_options=[
                "create_job",
                "list_jobs",
            ],
        )

    async def async_step_create_job(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle job creation."""
        errors = {}

        if user_input is not None:
            try:
                if not user_input.get("name"):
                    errors["name"] = "name_required"
                elif user_input.get("trigger_type") == TRIGGER_TYPE_SCHEDULE:
                    if not user_input.get("cron_expression"):
                        errors["cron_expression"] = "cron_required"
                elif user_input.get("trigger_type") == TRIGGER_TYPE_FREQUENCY:
                    if not user_input.get("days_interval") or user_input.get("days_interval") <= 0:
                        errors["days_interval"] = "days_required"

                if not errors:
                    # Load existing jobs
                    store = self.hass.helpers.storage.Store(
                        self.hass, 1, f"{DOMAIN}.jobs_{self.config_entry.entry_id}"
                    )
                    jobs_data = await store.async_load() or {"jobs": []}

                    # Create new job
                    job_id = str(uuid.uuid4())[:8]
                    new_job = {
                        "id": job_id,
                        "name": user_input["name"],
                        "trigger_type": user_input["trigger_type"],
                        "cron_expression": user_input.get("cron_expression"),
                        "days_interval": user_input.get("days_interval"),
                        "image": user_input.get("image"),
                        "priority": user_input.get("priority", 0),
                    }

                    jobs_data["jobs"].append(new_job)
                    await store.async_save(jobs_data)

                    _LOGGER.info("Job created: %s", new_job["name"])
                    return self.async_abort(reason="job_created")

            except Exception as e:
                _LOGGER.error("Error creating job: %s", e)
                errors["base"] = "unknown"

        trigger_type = user_input.get("trigger_type", TRIGGER_TYPE_SCHEDULE) if user_input else TRIGGER_TYPE_SCHEDULE

        schema_dict = {
            vol.Required("name"): cv.string,
            vol.Required("trigger_type", default=trigger_type): vol.In(
                {TRIGGER_TYPE_SCHEDULE: "Schedule (Cron)", TRIGGER_TYPE_FREQUENCY: "Frequency (Days)"}
            ),
        }

        if trigger_type == TRIGGER_TYPE_SCHEDULE:
            schema_dict[vol.Optional("cron_expression", default="0 0 * * *")] = cv.string
        else:
            schema_dict[vol.Optional("days_interval", default=7)] = cv.positive_int

        schema_dict.update({
            vol.Optional("image"): cv.string,
            vol.Optional("priority", default=0): cv.positive_int,
        })

        return self.async_show_form(
            step_id="create_job",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def async_step_list_jobs(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Show list of jobs to edit or delete."""
        store = self.hass.helpers.storage.Store(
            self.hass, 1, f"{DOMAIN}.jobs_{self.config_entry.entry_id}"
        )
        jobs_data = await store.async_load() or {"jobs": []}
        jobs = jobs_data.get("jobs", [])

        if not jobs:
            return self.async_abort(reason="no_jobs")

        menu_options = {job["id"]: job["name"] for job in jobs}

        if user_input is not None:
            selected_job_id = user_input.get("job_id")
            return await self.async_step_edit_job(job_id=selected_job_id)

        return self.async_show_menu(
            step_id="list_jobs",
            menu_options=menu_options,
        )

    async def async_step_edit_job(
        self, user_input: Optional[Dict[str, Any]] = None, job_id: Optional[str] = None
    ) -> FlowResult:
        """Handle job editing."""
        if not job_id:
            return self.async_abort(reason="job_not_found")

        store = self.hass.helpers.storage.Store(
            self.hass, 1, f"{DOMAIN}.jobs_{self.config_entry.entry_id}"
        )
        jobs_data = await store.async_load() or {"jobs": []}
        jobs = jobs_data.get("jobs", [])

        job = next((j for j in jobs if j["id"] == job_id), None)
        if not job:
            return self.async_abort(reason="job_not_found")

        errors = {}

        if user_input is not None:
            if user_input.get("action") == "delete":
                # Delete job
                jobs_data["jobs"] = [j for j in jobs if j["id"] != job_id]
                await store.async_save(jobs_data)
                _LOGGER.info("Job deleted: %s", job["name"])
                return self.async_abort(reason="job_deleted")

            elif user_input.get("action") == "update":
                # Update job
                try:
                    if not user_input.get("name"):
                        errors["name"] = "name_required"
                    elif user_input.get("trigger_type") == TRIGGER_TYPE_SCHEDULE:
                        if not user_input.get("cron_expression"):
                            errors["cron_expression"] = "cron_required"
                    elif user_input.get("trigger_type") == TRIGGER_TYPE_FREQUENCY:
                        if not user_input.get("days_interval") or user_input.get("days_interval") <= 0:
                            errors["days_interval"] = "days_required"

                    if not errors:
                        # Update the job
                        job_index = next((i for i, j in enumerate(jobs) if j["id"] == job_id), None)
                        if job_index is not None:
                            jobs[job_index].update({
                                "name": user_input["name"],
                                "trigger_type": user_input["trigger_type"],
                                "cron_expression": user_input.get("cron_expression"),
                                "days_interval": user_input.get("days_interval"),
                                "image": user_input.get("image"),
                                "priority": user_input.get("priority", 0),
                            })
                            await store.async_save(jobs_data)
                            _LOGGER.info("Job updated: %s", job["name"])
                            return self.async_abort(reason="job_updated")
                except Exception as e:
                    _LOGGER.error("Error updating job: %s", e)
                    errors["base"] = "unknown"

        trigger_type = job.get("trigger_type", TRIGGER_TYPE_SCHEDULE)

        schema_dict = {
            vol.Required("name", default=job.get("name")): cv.string,
            vol.Required("trigger_type", default=trigger_type): vol.In(
                {TRIGGER_TYPE_SCHEDULE: "Schedule (Cron)", TRIGGER_TYPE_FREQUENCY: "Frequency (Days)"}
            ),
        }

        if trigger_type == TRIGGER_TYPE_SCHEDULE:
            schema_dict[vol.Optional("cron_expression", default=job.get("cron_expression", "0 0 * * *"))] = cv.string
        else:
            schema_dict[vol.Optional("days_interval", default=job.get("days_interval", 7))] = cv.positive_int

        schema_dict.update({
            vol.Optional("image", default=job.get("image", "")): cv.string,
            vol.Optional("priority", default=job.get("priority", 0)): cv.positive_int,
            vol.Required("action", default="update"): vol.In(
                {"update": "Save Changes", "delete": "Delete Job"}
            ),
        })

        return self.async_show_form(
            step_id="edit_job",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )
