"""Quiz-related options flow steps for Raven Castle Tools."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
import uuid

import voluptuous as vol
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.util.dt import utcnow

from .const import DOMAIN, STORAGE_VERSION


class QuizOptionsFlowMixin:
    """Mixin adding quiz management steps to an options flow."""

    async def async_step_manage_quiz(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Show RC Quiz management menu."""
        return self.async_show_menu(
            step_id="manage_quiz",
            menu_options=["add_player", "list_players"],
        )

    async def async_step_add_player(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle player creation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input.get("name"):
                errors["name"] = "name_required"
            if not user_input.get("alias"):
                errors["alias"] = "alias_required"

            if not errors:
                store = self.hass.helpers.storage.Store(
                    self.hass,
                    STORAGE_VERSION,
                    f"{DOMAIN}.quiz_{self.config_entry.entry_id}",
                )
                players_data = await store.async_load() or {"players": []}
                players = players_data.get("players", [])

                players.append(
                    {
                        "id": str(uuid.uuid4())[:8],
                        "name": user_input["name"],
                        "alias": user_input["alias"],
                        "photo": user_input.get("photo", ""),
                        "total_score": 0,
                        "current_round_score": 0,
                        "last_round_score": 0,
                        "enabled": True,
                        "created": datetime.isoformat(utcnow()),
                    }
                )

                await store.async_save({"players": players})
                return self.async_abort(reason="player_created")

        return self.async_show_form(
            step_id="add_player",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): cv.string,
                    vol.Required("alias"): cv.string,
                    vol.Optional("photo", default=""): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_list_players(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Show player picker for editing/deleting."""
        store = self.hass.helpers.storage.Store(
            self.hass,
            STORAGE_VERSION,
            f"{DOMAIN}.quiz_{self.config_entry.entry_id}",
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
        user_input: Optional[dict[str, Any]] = None,
        player_id: Optional[str] = None,
    ) -> FlowResult:
        """Edit or delete a quiz player."""
        if player_id:
            self._editing_player_id = player_id
        else:
            player_id = getattr(self, "_editing_player_id", None)

        if not player_id:
            return self.async_abort(reason="player_not_found")

        store = self.hass.helpers.storage.Store(
            self.hass,
            STORAGE_VERSION,
            f"{DOMAIN}.quiz_{self.config_entry.entry_id}",
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
                        "photo": user_input.get("photo", ""),
                        "enabled": bool(user_input.get("enabled", False)),
                    }
                )
                await store.async_save(players_data)
                return self.async_abort(reason="player_updated")

        return self.async_show_form(
            step_id="edit_player",
            data_schema=vol.Schema(
                {
                    vol.Required("name", default=player.get("name", "")): cv.string,
                    vol.Required("alias", default=player.get("alias", "")): cv.string,
                    vol.Optional("photo", default=player.get("photo", "")): cv.string,
                    vol.Required("enabled", default=bool(player.get("enabled", False))): bool,
                    vol.Required("action", default="update"): vol.In(
                        {"update": "Save Changes", "delete": "Delete Player"}
                    ),
                }
            ),
            errors=errors,
        )
