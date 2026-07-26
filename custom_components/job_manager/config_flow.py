"""Config flow for Job Manager."""
import logging
from typing import Any, Dict, Optional
import uuid

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, TRIGGER_TYPE_SCHEDULE, TRIGGER_TYPE_FREQUENCY

_LOGGER = logging.getLogger(__name__)


class JobManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Job Manager."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Check if user wants to create a job or just set up the integration
            if user_input.get("setup_integration"):
                return self.async_create_entry(title="Job Manager", data={})
            else:
                # Go to job creation step
                return await self.async_step_create_job()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("setup_integration", default=True): cv.boolean,
            }),
            description_placeholders={
                "setup_info": "Select 'No' to create a job, or 'Yes' to just set up the integration."
            },
        )

    async def async_step_create_job(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle job creation step."""
        errors = {}

        if user_input is not None:
            try:
                # Validate input
                if not user_input.get("name"):
                    errors["name"] = "name_required"
                
                if user_input.get("trigger_type") == TRIGGER_TYPE_SCHEDULE:
                    if not user_input.get("cron_expression"):
                        errors["cron_expression"] = "cron_required"
                elif user_input.get("trigger_type") == TRIGGER_TYPE_FREQUENCY:
                    if not user_input.get("days_interval"):
                        errors["days_interval"] = "days_required"

                if not errors:
                    # Store the job in Home Assistant storage
                    job_id = str(uuid.uuid4())[:8]
                    job_data = {
                        "id": job_data_id,
                        "name": user_input["name"],
                        "trigger_type": user_input["trigger_type"],
                        "cron_expression": user_input.get("cron_expression"),
                        "days_interval": user_input.get("days_interval"),
                        "image": user_input.get("image"),
                        "priority": user_input.get("priority", 0),
                    }
                    
                    _LOGGER.info(f"Job created: {job_data}")
                    return self.async_abort(reason="job_created")

            except Exception as e:
                _LOGGER.error(f"Error creating job: {e}")
                errors["base"] = "unknown"

        trigger_type = "schedule"  # Default

        schema = {
            vol.Required("name"): cv.string,
            vol.Required("trigger_type", default=trigger_type): vol.In(
                {TRIGGER_TYPE_SCHEDULE: "Schedule (Cron)", TRIGGER_TYPE_FREQUENCY: "Frequency (Days)"}
            ),
        }

        if trigger_type == TRIGGER_TYPE_SCHEDULE:
            schema[vol.Optional("cron_expression", default="0 0 * * *")] = cv.string
        else:
            schema[vol.Optional("days_interval", default=7)] = cv.positive_int

        schema.update({
            vol.Optional("image"): cv.string,
            vol.Optional("priority", default=0): cv.integer,
        })

        return self.async_show_form(
            step_id="create_job",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "trigger_info": "Choose schedule (cron) or frequency (days interval)"
            },
        )
