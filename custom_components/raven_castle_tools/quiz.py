"""RC Quiz logic and sensor entities."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
import uuid

import voluptuous as vol
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import (
    ATTR_LAST_ROUND_SCORE,
    ATTR_PLAYER_ALIAS,
    ATTR_PLAYER_ENABLED,
    ATTR_PLAYER_NAME,
    ATTR_PLAYER_PHOTO,
    ATTR_ROUND_SCORE,
    ATTR_TOTAL_SCORE,
    DOMAIN,
    PREFIX_QUIZ,
    SERVICE_ADD_PLAYER,
    SERVICE_ADD_POINTS,
    SERVICE_DISABLE_PLAYER,
    SERVICE_ENABLE_PLAYER,
    SERVICE_REMOVE_PLAYER,
    SERVICE_REMOVE_POINTS,
    SERVICE_RESET_QUIZ,
    SERVICE_START_NEW_QUIZ,
    SERVICE_START_NEW_ROUND,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

QUIZ_SIGNAL_UPDATE = f"{DOMAIN}_quiz_update"


def _quiz_storage_key(entry_id: str) -> str:
    return f"{DOMAIN}.quiz_{entry_id}"


def _normalize_players(players_data: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    players: dict[str, dict[str, Any]] = {}
    raw_players = (players_data or {}).get("players", [])
    for player in raw_players:
        player_id = player.get("id")
        if not player_id:
            continue
        players[player_id] = {
            "id": player_id,
            "name": player.get("name", ""),
            "alias": player.get("alias", ""),
            "photo": player.get("photo", ""),
            "total_score": int(player.get("total_score", 0)),
            "current_round_score": int(player.get("current_round_score", 0)),
            "last_round_score": int(player.get("last_round_score", 0)),
            "enabled": bool(player.get("enabled", False)),
            "created": player.get("created") or datetime.isoformat(utcnow()),
        }
    return players


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up quiz sensors from a config entry."""
    store = hass.helpers.storage.Store(hass, STORAGE_VERSION, _quiz_storage_key(config_entry.entry_id))
    players_data = await store.async_load() or {"players": []}
    players = _normalize_players(players_data)

    hass.data[DOMAIN][config_entry.entry_id]["quiz_store"] = store
    hass.data[DOMAIN][config_entry.entry_id]["quiz_players"] = players
    hass.data[DOMAIN][config_entry.entry_id]["quiz_entities"] = {}
    hass.data[DOMAIN][config_entry.entry_id]["quiz_add_entities"] = async_add_entities

    entities: list[SensorEntity] = []
    for player_id in players:
        entities.extend(_build_player_entities(hass, config_entry.entry_id, player_id))

    if entities:
        async_add_entities(entities)

    _store_entity_references(hass, config_entry.entry_id, entities)


async def async_setup_quiz_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register RC Quiz services."""

    async def _save_players(entry_id: str) -> None:
        data = hass.data[DOMAIN][entry_id]
        store = data["quiz_store"]
        players = data["quiz_players"]
        await store.async_save({"players": list(players.values())})

    async def _broadcast_update(entry_id: str) -> None:
        async_dispatcher_send(hass, f"{QUIZ_SIGNAL_UPDATE}_{entry_id}")

    def _parse_player_id(entity_id: str | None, player_id: str | None) -> str | None:
        if player_id:
            return player_id
        if not entity_id:
            return None
        prefix = f"sensor.{PREFIX_QUIZ}_"
        if not entity_id.startswith(prefix):
            return None
        player_part = entity_id[len(prefix) :]
        if player_part.endswith("_round"):
            player_part = player_part[: -len("_round")]
        return player_part

    def _iter_quiz_entries() -> list[tuple[str, dict[str, Any]]]:
        return [
            (entry_id, data)
            for entry_id, data in hass.data.get(DOMAIN, {}).items()
            if isinstance(data, dict) and "quiz_players" in data
        ]

    async def _add_player(call: ServiceCall) -> None:
        player_id = str(uuid.uuid4())[:8]
        player = {
            "id": player_id,
            "name": call.data["name"],
            "alias": call.data["alias"],
            "photo": call.data.get("photo", ""),
            "total_score": 0,
            "current_round_score": 0,
            "last_round_score": 0,
            "enabled": True,
            "created": datetime.isoformat(utcnow()),
        }

        for entry_id, data in _iter_quiz_entries():
            data["quiz_players"][player_id] = player
            new_entities = _build_player_entities(hass, entry_id, player_id)
            data["quiz_add_entities"](new_entities)
            _store_entity_references(hass, entry_id, new_entities)
            await _save_players(entry_id)
            await _broadcast_update(entry_id)
            return

    async def _remove_player(call: ServiceCall) -> None:
        target_player_id = _parse_player_id(call.data.get("entity_id"), call.data.get("player_id"))
        if not target_player_id:
            return

        for entry_id, data in _iter_quiz_entries():
            if target_player_id not in data["quiz_players"]:
                continue

            data["quiz_players"].pop(target_player_id)

            entities = data["quiz_entities"].pop(target_player_id, [])
            for entity in entities:
                await entity.async_remove()

            await _save_players(entry_id)
            await _broadcast_update(entry_id)
            return

    async def _set_player_enabled(call: ServiceCall, enabled: bool) -> None:
        target_player_id = _parse_player_id(call.data.get("entity_id"), call.data.get("player_id"))
        if not target_player_id:
            return

        for entry_id, data in _iter_quiz_entries():
            player = data["quiz_players"].get(target_player_id)
            if not player:
                continue
            player["enabled"] = enabled
            await _save_players(entry_id)
            await _broadcast_update(entry_id)
            return

    async def _change_points(call: ServiceCall, multiplier: int) -> None:
        target_player_id = _parse_player_id(call.data.get("entity_id"), call.data.get("player_id"))
        if not target_player_id:
            return

        points = int(call.data["points"]) * multiplier
        for entry_id, data in _iter_quiz_entries():
            player = data["quiz_players"].get(target_player_id)
            if not player:
                continue
            player["current_round_score"] = int(player.get("current_round_score", 0)) + points
            await _save_players(entry_id)
            await _broadcast_update(entry_id)
            return

    async def _enable_player(call: ServiceCall) -> None:
        await _set_player_enabled(call, True)

    async def _disable_player(call: ServiceCall) -> None:
        await _set_player_enabled(call, False)

    async def _add_points(call: ServiceCall) -> None:
        await _change_points(call, 1)

    async def _remove_points(call: ServiceCall) -> None:
        await _change_points(call, -1)

    async def _start_new_round(call: ServiceCall) -> None:
        del call
        for entry_id, data in _iter_quiz_entries():
            for player in data["quiz_players"].values():
                if not player.get("enabled"):
                    continue
                round_score = int(player.get("current_round_score", 0))
                player["last_round_score"] = round_score
                player["total_score"] = int(player.get("total_score", 0)) + round_score
                player["current_round_score"] = 0
            await _save_players(entry_id)
            await _broadcast_update(entry_id)

    async def _start_new_quiz(call: ServiceCall) -> None:
        del call
        for entry_id, data in _iter_quiz_entries():
            for player in data["quiz_players"].values():
                player["total_score"] = 0
                player["current_round_score"] = 0
                player["last_round_score"] = 0
            await _save_players(entry_id)
            await _broadcast_update(entry_id)

    async def _reset_quiz(call: ServiceCall) -> None:
        del call
        for entry_id, data in _iter_quiz_entries():
            for player in data["quiz_players"].values():
                player["total_score"] = 0
                player["current_round_score"] = 0
                player["last_round_score"] = 0
                player["enabled"] = False
            await _save_players(entry_id)
            await _broadcast_update(entry_id)

    if not hass.services.has_service(DOMAIN, SERVICE_ADD_PLAYER):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ADD_PLAYER,
            _add_player,
            schema=vol.Schema(
                {
                    vol.Required("name"): cv.string,
                    vol.Required("alias"): cv.string,
                    vol.Optional("photo", default=""): cv.string,
                }
            ),
        )

    target_schema = vol.Schema(
        {
            vol.Optional("entity_id"): cv.entity_id,
            vol.Optional("player_id"): cv.string,
        }
    )

    if not hass.services.has_service(DOMAIN, SERVICE_REMOVE_PLAYER):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REMOVE_PLAYER,
            _remove_player,
            schema=target_schema,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_ENABLE_PLAYER):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ENABLE_PLAYER,
            _enable_player,
            schema=target_schema,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_DISABLE_PLAYER):
        hass.services.async_register(
            DOMAIN,
            SERVICE_DISABLE_PLAYER,
            _disable_player,
            schema=target_schema,
        )

    points_schema = vol.Schema(
        {
            vol.Optional("entity_id"): cv.entity_id,
            vol.Optional("player_id"): cv.string,
            vol.Required("points"): vol.Coerce(int),
        }
    )

    if not hass.services.has_service(DOMAIN, SERVICE_ADD_POINTS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ADD_POINTS,
            _add_points,
            schema=points_schema,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_REMOVE_POINTS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REMOVE_POINTS,
            _remove_points,
            schema=points_schema,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_START_NEW_ROUND):
        hass.services.async_register(DOMAIN, SERVICE_START_NEW_ROUND, _start_new_round)

    if not hass.services.has_service(DOMAIN, SERVICE_START_NEW_QUIZ):
        hass.services.async_register(DOMAIN, SERVICE_START_NEW_QUIZ, _start_new_quiz)

    if not hass.services.has_service(DOMAIN, SERVICE_RESET_QUIZ):
        hass.services.async_register(DOMAIN, SERVICE_RESET_QUIZ, _reset_quiz)


def _build_player_entities(
    hass: HomeAssistant,
    entry_id: str,
    player_id: str,
) -> list[SensorEntity]:
    return [
        QuizPlayerSensor(hass, entry_id, player_id),
        QuizRoundScoreSensor(hass, entry_id, player_id),
    ]


def _store_entity_references(
    hass: HomeAssistant,
    entry_id: str,
    entities: list[SensorEntity],
) -> None:
    by_player = hass.data[DOMAIN][entry_id].setdefault("quiz_entities", {})
    for entity in entities:
        player_id = getattr(entity, "player_id", None)
        if not player_id:
            continue
        player_entities = by_player.setdefault(player_id, [])
        player_entities.append(entity)


class QuizBaseSensor(SensorEntity):
    """Base class for quiz sensors."""

    def __init__(self, hass: HomeAssistant, entry_id: str, player_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.player_id = player_id

    @property
    def _player(self) -> dict[str, Any] | None:
        return (
            self.hass.data.get(DOMAIN, {})
            .get(self.entry_id, {})
            .get("quiz_players", {})
            .get(self.player_id)
        )

    @property
    def available(self) -> bool:
        return self._player is not None

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""

        @callback
        def _handle_update() -> None:
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{QUIZ_SIGNAL_UPDATE}_{self.entry_id}",
                _handle_update,
            )
        )


class QuizPlayerSensor(QuizBaseSensor):
    """Main player sensor containing total score and metadata."""

    def __init__(self, hass: HomeAssistant, entry_id: str, player_id: str) -> None:
        super().__init__(hass, entry_id, player_id)
        self._attr_unique_id = f"{DOMAIN}_quiz_{entry_id}_{player_id}_total"
        self.entity_id = f"sensor.{PREFIX_QUIZ}_{player_id}"

    @property
    def name(self) -> str:
        player = self._player or {}
        return player.get("name") or f"RC Quiz {self.player_id}"

    @property
    def native_value(self) -> int | None:
        player = self._player
        if not player:
            return None
        return int(player.get("total_score", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        player = self._player or {}
        return {
            "name": player.get("name", ""),
            "alias": player.get("alias", ""),
            "photo": player.get("photo", ""),
            "enabled": bool(player.get("enabled", False)),
            "current_round_score": int(player.get("current_round_score", 0)),
            "last_round_score": int(player.get("last_round_score", 0)),
            "created": player.get("created"),
        }


class QuizRoundScoreSensor(QuizBaseSensor):
    """Player current round score sensor."""

    def __init__(self, hass: HomeAssistant, entry_id: str, player_id: str) -> None:
        super().__init__(hass, entry_id, player_id)
        self._attr_unique_id = f"{DOMAIN}_quiz_{entry_id}_{player_id}_round"
        self.entity_id = f"sensor.{PREFIX_QUIZ}_{player_id}_round"

    @property
    def name(self) -> str:
        player = self._player or {}
        player_alias = player.get("alias") or self.player_id
        return f"{player_alias} Round Score"

    @property
    def native_value(self) -> int | None:
        player = self._player
        if not player:
            return None
        return int(player.get("current_round_score", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        player = self._player or {}
        return {
            ATTR_PLAYER_NAME: player.get("name", ""),
            ATTR_PLAYER_ALIAS: player.get("alias", ""),
            ATTR_PLAYER_PHOTO: player.get("photo", ""),
            ATTR_PLAYER_ENABLED: bool(player.get("enabled", False)),
            ATTR_TOTAL_SCORE: int(player.get("total_score", 0)),
            ATTR_ROUND_SCORE: int(player.get("current_round_score", 0)),
            ATTR_LAST_ROUND_SCORE: int(player.get("last_round_score", 0)),
        }
