"""Config flow for Raven House Tools."""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import utcnow

from .const import (
    CONF_FEATURE,
    DOMAIN,
    FEATURE_JOBS,
    FEATURE_QUIZ,
    STORAGE_VERSION,
    TRIGGER_TYPE_FREQUENCY,
    TRIGGER_TYPE_MANUAL,
    TRIGGER_TYPE_SCHEDULE,
)
from .entities import _jobs_storage_key, async_sync_jobs_from_storage
from .features import get_entry_feature
from .quiz_entities import _quiz_storage_key, async_sync_players_from_storage


def _normalize_media_value(value: Any) -> str:
    """Normalize media selector output into a storable path/URL."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        media_id = value.get("media_content_id")
        if isinstance(media_id, str):
            return media_id.strip()
    return ""


class RavenHouseJobsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Raven House Tools."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            feature = user_input[CONF_FEATURE]
            await self.async_set_unique_id(feature)
            self._abort_if_unique_id_configured()

            title = "RH Jobs" if feature == FEATURE_JOBS else "RH Quiz"
            return self.async_create_entry(title=title, data={CONF_FEATURE: feature})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_FEATURE): vol.In(
                        {
                            FEATURE_JOBS: "RH Jobs",
                            FEATURE_QUIZ: "RH Quiz",
                        }
                    )
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return RavenHouseJobsOptionsFlow(config_entry)


class RavenHouseJobsOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Raven House Tools."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry
        self._editing_job_id: str | None = None
        self._editing_player_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage jobs and quiz players."""
        del user_input
        feature = get_entry_feature(self._config_entry)
        if feature == FEATURE_JOBS:
            return await self.async_step_create_job()
        if feature == FEATURE_QUIZ:
            return await self.async_step_add_player()

        return self.async_show_menu(
            step_id="init",
            menu_options=["create_job", "add_player"],
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
                        "image": _normalize_media_value(user_input.get("image", "")),
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
                            TRIGGER_TYPE_MANUAL: "Manual",
                        }
                    ),
                    vol.Optional("cron_expression", default="0 0 * * *"): cv.string,
                    vol.Optional("days_interval", default=7): cv.positive_int,
                    vol.Optional("image", default=""): selector.selector(
                        {"media": {"accept": ["image/*"]}}
                    ),
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
                        "image": _normalize_media_value(user_input.get("image", "")),
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
                            TRIGGER_TYPE_MANUAL: "Manual",
                        }
                    ),
                    vol.Optional(
                        "cron_expression",
                        default=job.get("cron_expression", "0 0 * * *"),
                    ): cv.string,
                    vol.Optional(
                        "days_interval", default=job.get("days_interval", 7)
                    ): cv.positive_int,
                    vol.Optional(
                        "image", default=job.get("image", "")
                    ): selector.selector({"media": {"accept": ["image/*"]}}),
                    vol.Optional("priority", default=job.get("priority", 0)): cv.positive_int,
                    vol.Required("action", default="update"): vol.In(
                        {"update": "Save Changes", "delete": "Delete Job"}
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_add_player(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle player creation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input.get("name"):
                errors["name"] = "name_required"
            if not user_input.get("alias"):
                errors["alias"] = "alias_required"

            if not errors:
                store = Store(
                    self.hass,
                    STORAGE_VERSION,
                    _quiz_storage_key(self._config_entry.entry_id),
                )
                players_data = await store.async_load() or {"players": []}
                players = players_data.get("players", [])
                players.append(
                    {
                        "id": str(uuid.uuid4())[:8],
                        "name": user_input["name"],
                        "alias": user_input["alias"],
                        "photo": _normalize_media_value(user_input.get("photo", "")),
                        "total_score": 0,
                        "current_round_score": 0,
                        "last_round_score": 0,
                        "enabled": True,
                        "created": utcnow().isoformat(),
                    }
                )
                await store.async_save({"players": players})
                await async_sync_players_from_storage(self.hass, self._config_entry.entry_id)
                return self.async_abort(reason="player_created")

        return self.async_show_form(
            step_id="add_player",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): cv.string,
                    vol.Required("alias"): cv.string,
                    vol.Optional("photo", default=""): selector.selector(
                        {"media": {"accept": ["image/*"]}}
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_list_players(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show player picker for editing."""
        store = Store(
            self.hass,
            STORAGE_VERSION,
            _quiz_storage_key(self._config_entry.entry_id),
        )
        players_data = await store.async_load() or {"players": []}
        players = players_data.get("players", [])

        if not players:
            return self.async_abort(reason="no_players")

        choices = {
            player["id"]: f"{player.get('name', '')} ({player.get('alias', '')})"
            for player in players
        }
        if user_input is not None:
            return await self.async_step_edit_player(player_id=user_input.get("player_id"))

        return self.async_show_form(
            step_id="list_players",
            data_schema=vol.Schema({vol.Required("player_id"): vol.In(choices)}),
        )

    async def async_step_edit_player(
        self,
        user_input: dict[str, Any] | None = None,
        player_id: str | None = None,
    ) -> FlowResult:
        """Edit or delete a player."""
        if player_id:
            self._editing_player_id = player_id
        else:
            player_id = self._editing_player_id

        if not player_id:
            return self.async_abort(reason="player_not_found")

        store = Store(
            self.hass,
            STORAGE_VERSION,
            _quiz_storage_key(self._config_entry.entry_id),
        )
        players_data = await store.async_load() or {"players": []}
        players = players_data.get("players", [])
        player = next((item for item in players if item.get("id") == player_id), None)
        if not player:
            return self.async_abort(reason="player_not_found")

        errors: dict[str, str] = {}
        if user_input is not None:
            action = user_input.get("action", "update")
            if action == "delete":
                players_data["players"] = [
                    item for item in players if item.get("id") != player_id
                ]
                await store.async_save(players_data)
                await async_sync_players_from_storage(self.hass, self._config_entry.entry_id)
                return self.async_abort(reason="player_deleted")

            if not user_input.get("name"):
                errors["name"] = "name_required"
            if not user_input.get("alias"):
                errors["alias"] = "alias_required"

            if not errors:
                player.update(
                    {
                        "name": user_input["name"],
                        "alias": user_input["alias"],
                        "photo": _normalize_media_value(user_input.get("photo", "")),
                        "enabled": bool(user_input.get("enabled", False)),
                    }
                )
                await store.async_save(players_data)
                await async_sync_players_from_storage(self.hass, self._config_entry.entry_id)
                return self.async_abort(reason="player_updated")

        return self.async_show_form(
            step_id="edit_player",
            data_schema=vol.Schema(
                {
                    vol.Required("name", default=player.get("name", "")): cv.string,
                    vol.Required("alias", default=player.get("alias", "")): cv.string,
                    vol.Optional(
                        "photo", default=player.get("photo", "")
                    ): selector.selector({"media": {"accept": ["image/*"]}}),
                    vol.Required("enabled", default=bool(player.get("enabled", False))): bool,
                    vol.Required("action", default="update"): vol.In(
                        {"update": "Save Changes", "delete": "Delete Player"}
                    ),
                }
            ),
            errors=errors,
        )
