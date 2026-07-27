"""Entity model for Raven Castle Quiz support within Raven Castle Tools."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any
import uuid

import voluptuous as vol
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import utcnow

from .quiz_const import (
    ATTR_CREATED,
    ATTR_LAST_ROUND_SCORE,
    ATTR_PLAYER_ALIAS,
    ATTR_PLAYER_ENABLED,
    ATTR_PLAYER_ID,
    ATTR_PLAYER_METRIC,
    ATTR_PLAYER_NAME,
    ATTR_PLAYER_PHOTO,
    ATTR_ROUND_SCORE,
    ATTR_TOTAL_SCORE,
    DOMAIN,
    PREFIX_QUIZ,
    QUIZ_SIGNAL_UPDATE,
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


def _quiz_storage_key(entry_id: str) -> str:
    return f"{DOMAIN}.players_{entry_id}"


def _entry_data(hass: HomeAssistant, entry_id: str) -> dict[str, Any]:
    return hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})


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
            "created": player.get("created") or utcnow().isoformat(),
        }
    return players


async def _ensure_runtime(hass: HomeAssistant, entry_id: str) -> dict[str, Any]:
    data = _entry_data(hass, entry_id)
    if "quiz_store" not in data:
        data["quiz_store"] = Store(hass, STORAGE_VERSION, _quiz_storage_key(entry_id))
    if "quiz_players" not in data:
        players_data = await data["quiz_store"].async_load() or {"players": []}
        data["quiz_players"] = _normalize_players(players_data)
    data.setdefault("quiz_sensor_entities", {})
    data.setdefault("quiz_binary_entities", {})
    return data


async def _save_players(hass: HomeAssistant, entry_id: str) -> None:
    data = await _ensure_runtime(hass, entry_id)
    await data["quiz_store"].async_save({"players": list(data["quiz_players"].values())})


async def async_setup_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up player sensors."""
    data = await _ensure_runtime(hass, config_entry.entry_id)
    data["quiz_sensor_add_entities"] = async_add_entities

    entities: list[SensorEntity] = []
    for player_id in sorted(data["quiz_players"]):
        entities.extend(_build_player_sensor_entities(hass, config_entry.entry_id, player_id))

    if entities:
        async_add_entities(entities)
        _store_sensor_entities(data, entities)


async def async_setup_binary_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up player binary sensors."""
    data = await _ensure_runtime(hass, config_entry.entry_id)
    data["quiz_binary_add_entities"] = async_add_entities

    entities = [
        QuizPlayerEnabledBinarySensor(hass, config_entry.entry_id, player_id)
        for player_id in sorted(data["quiz_players"])
    ]
    if entities:
        async_add_entities(entities)
        for entity in entities:
            data["quiz_binary_entities"][entity.player_id] = entity


def _build_player_sensor_entities(
    hass: HomeAssistant,
    entry_id: str,
    player_id: str,
) -> list[SensorEntity]:
    return [
        QuizTotalScoreSensor(hass, entry_id, player_id),
        QuizRoundScoreSensor(hass, entry_id, player_id),
        QuizLastRoundScoreSensor(hass, entry_id, player_id),
        QuizAliasSensor(hass, entry_id, player_id),
    ]


def _store_sensor_entities(data: dict[str, Any], entities: list[SensorEntity]) -> None:
    by_player = data.setdefault("quiz_sensor_entities", {})
    for entity in entities:
        by_player.setdefault(entity.player_id, []).append(entity)


def _entity_player_id(entity_id: str) -> str | None:
    sensor_prefix = f"sensor.{PREFIX_QUIZ}_"
    binary_prefix = f"binary_sensor.{PREFIX_QUIZ}_"

    if entity_id.startswith(sensor_prefix):
        player_part = entity_id[len(sensor_prefix) :]
    elif entity_id.startswith(binary_prefix):
        player_part = entity_id[len(binary_prefix) :]
    else:
        return None

    for suffix in ("_round", "_last_round", "_alias", "_enabled"):
        if player_part.endswith(suffix):
            return player_part[: -len(suffix)]
    return player_part


def _find_player_by_target(
    hass: HomeAssistant, entity_id: str | None, player_id: str | None
) -> tuple[str, dict[str, Any], dict[str, Any]] | None:
    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        players = data.get("quiz_players", {})
        if player_id and player_id in players:
            return entry_id, data, players[player_id]
        if entity_id:
            parsed_player_id = _entity_player_id(entity_id)
            if parsed_player_id and parsed_player_id in players:
                return entry_id, data, players[parsed_player_id]
    return None


async def async_setup_quiz_services(hass: HomeAssistant) -> None:
    """Register Raven Castle Quiz services."""

    async def _broadcast(entry_id: str, player_id: str | None = None) -> None:
        if player_id is not None:
            async_dispatcher_send(hass, f"{QUIZ_SIGNAL_UPDATE}_{entry_id}_{player_id}")
            return
        data = await _ensure_runtime(hass, entry_id)
        for existing_player_id in data.get("quiz_players", {}):
            async_dispatcher_send(hass, f"{QUIZ_SIGNAL_UPDATE}_{entry_id}_{existing_player_id}")

    async def _add_player(call: ServiceCall) -> None:
        player = {
            "id": str(uuid.uuid4())[:8],
            "name": call.data["name"],
            "alias": call.data["alias"],
            "photo": call.data.get("photo", ""),
            "total_score": 0,
            "current_round_score": 0,
            "last_round_score": 0,
            "enabled": True,
            "created": utcnow().isoformat(),
        }

        for entry_id in hass.data.get(DOMAIN, {}):
            data = await _ensure_runtime(hass, entry_id)
            data["quiz_players"][player["id"]] = player
            await _save_players(hass, entry_id)

            sensor_add = data.get("quiz_sensor_add_entities")
            if sensor_add:
                sensor_entities = _build_player_sensor_entities(hass, entry_id, player["id"])
                sensor_add(sensor_entities)
                _store_sensor_entities(data, sensor_entities)

            binary_add = data.get("quiz_binary_add_entities")
            if binary_add:
                binary_entity = QuizPlayerEnabledBinarySensor(hass, entry_id, player["id"])
                binary_add([binary_entity])
                data["quiz_binary_entities"][player["id"]] = binary_entity

            await _broadcast(entry_id, player["id"])
            return

    async def _remove_player(call: ServiceCall) -> None:
        result = _find_player_by_target(hass, call.data.get("entity_id"), call.data.get("player_id"))
        if result is None:
            return
        entry_id, data, player = result
        player_id = player["id"]
        data["quiz_players"].pop(player_id, None)

        for entity in data.get("quiz_sensor_entities", {}).pop(player_id, []):
            await entity.async_remove()
        binary_entity = data.get("quiz_binary_entities", {}).pop(player_id, None)
        if binary_entity is not None:
            await binary_entity.async_remove()

        await _save_players(hass, entry_id)

    async def _set_enabled(call: ServiceCall, enabled: bool) -> None:
        result = _find_player_by_target(hass, call.data.get("entity_id"), call.data.get("player_id"))
        if result is None:
            return
        entry_id, _, player = result
        player["enabled"] = enabled
        await _save_players(hass, entry_id)
        await _broadcast(entry_id, player["id"])

    async def _enable_player(call: ServiceCall) -> None:
        await _set_enabled(call, True)

    async def _disable_player(call: ServiceCall) -> None:
        await _set_enabled(call, False)

    async def _change_points(call: ServiceCall, multiplier: int) -> None:
        result = _find_player_by_target(hass, call.data.get("entity_id"), call.data.get("player_id"))
        if result is None:
            return
        entry_id, _, player = result
        points = int(call.data["points"]) * multiplier
        player[ATTR_ROUND_SCORE] = int(player.get(ATTR_ROUND_SCORE, 0)) + points
        await _save_players(hass, entry_id)
        await _broadcast(entry_id, player["id"])

    async def _add_points(call: ServiceCall) -> None:
        await _change_points(call, 1)

    async def _remove_points(call: ServiceCall) -> None:
        await _change_points(call, -1)

    async def _start_new_round(call: ServiceCall) -> None:
        del call
        for entry_id in hass.data.get(DOMAIN, {}):
            data = await _ensure_runtime(hass, entry_id)
            for player in data["quiz_players"].values():
                if not player.get("enabled"):
                    continue
                round_score = int(player.get(ATTR_ROUND_SCORE, 0))
                player[ATTR_LAST_ROUND_SCORE] = round_score
                player[ATTR_TOTAL_SCORE] = int(player.get(ATTR_TOTAL_SCORE, 0)) + round_score
                player[ATTR_ROUND_SCORE] = 0
            await _save_players(hass, entry_id)
            await _broadcast(entry_id)

    async def _start_new_quiz(call: ServiceCall) -> None:
        del call
        for entry_id in hass.data.get(DOMAIN, {}):
            data = await _ensure_runtime(hass, entry_id)
            for player in data["quiz_players"].values():
                player[ATTR_TOTAL_SCORE] = 0
                player[ATTR_ROUND_SCORE] = 0
                player[ATTR_LAST_ROUND_SCORE] = 0
            await _save_players(hass, entry_id)
            await _broadcast(entry_id)

    async def _reset_quiz(call: ServiceCall) -> None:
        del call
        for entry_id in hass.data.get(DOMAIN, {}):
            data = await _ensure_runtime(hass, entry_id)
            for player in data["quiz_players"].values():
                player[ATTR_TOTAL_SCORE] = 0
                player[ATTR_ROUND_SCORE] = 0
                player[ATTR_LAST_ROUND_SCORE] = 0
                player[ATTR_PLAYER_ENABLED] = False
            await _save_players(hass, entry_id)
            await _broadcast(entry_id)

    target_schema = vol.Schema(
        {
            vol.Optional("entity_id"): cv.entity_id,
            vol.Optional("player_id"): cv.string,
        }
    )
    points_schema = vol.Schema(
        {
            vol.Optional("entity_id"): cv.entity_id,
            vol.Optional("player_id"): cv.string,
            vol.Required("points"): vol.Coerce(int),
        }
    )

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

    if not hass.services.has_service(DOMAIN, SERVICE_REMOVE_PLAYER):
        hass.services.async_register(DOMAIN, SERVICE_REMOVE_PLAYER, _remove_player, schema=target_schema)

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


async def async_sync_players_from_storage(hass: HomeAssistant, entry_id: str) -> None:
    """Synchronize runtime entities with stored players."""
    data = await _ensure_runtime(hass, entry_id)
    players_data = await data["quiz_store"].async_load() or {"players": []}
    new_players = _normalize_players(players_data)

    existing_ids = set(data["quiz_players"])
    new_ids = set(new_players)

    for removed_player_id in existing_ids - new_ids:
        for entity in data.get("quiz_sensor_entities", {}).pop(removed_player_id, []):
            await entity.async_remove()
        binary_entity = data.get("quiz_binary_entities", {}).pop(removed_player_id, None)
        if binary_entity is not None:
            await binary_entity.async_remove()

    for player_id in existing_ids & new_ids:
        data["quiz_players"][player_id].update(new_players[player_id])
        async_dispatcher_send(hass, f"{QUIZ_SIGNAL_UPDATE}_{entry_id}_{player_id}")

    data["quiz_players"].update({player_id: new_players[player_id] for player_id in new_ids - existing_ids})

    added_player_ids = sorted(new_ids - existing_ids)
    sensor_add = data.get("quiz_sensor_add_entities")
    if sensor_add and added_player_ids:
        sensor_entities: list[SensorEntity] = []
        for player_id in added_player_ids:
            sensor_entities.extend(_build_player_sensor_entities(hass, entry_id, player_id))
        sensor_add(sensor_entities)
        _store_sensor_entities(data, sensor_entities)

    binary_add = data.get("quiz_binary_add_entities")
    if binary_add and added_player_ids:
        binary_entities = [
            QuizPlayerEnabledBinarySensor(hass, entry_id, player_id)
            for player_id in added_player_ids
        ]
        binary_add(binary_entities)
        for entity in binary_entities:
            data["quiz_binary_entities"][entity.player_id] = entity


class QuizEntityBase:
    """Shared helpers for quiz entities."""

    def __init__(self, hass: HomeAssistant, entry_id: str, player_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.player_id = player_id

    @property
    def _player(self) -> dict[str, Any] | None:
        return _entry_data(self.hass, self.entry_id).get("quiz_players", {}).get(self.player_id)

    @property
    def _device_info(self) -> DeviceInfo:
        player = self._player or {}
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry_id}_{self.player_id}")},
            name=player.get("name") or f"RC Quiz {self.player_id}",
            manufacturer="Raven Castle",
            model="Raven Castle Quiz Player",
        )

    @property
    def device_info(self) -> DeviceInfo:
        return self._device_info

    def _common_attributes(self) -> dict[str, Any]:
        player = self._player or {}
        return {
            ATTR_PLAYER_ID: self.player_id,
            ATTR_PLAYER_NAME: player.get("name", ""),
            ATTR_PLAYER_ALIAS: player.get("alias", ""),
            ATTR_PLAYER_PHOTO: player.get("photo", ""),
            ATTR_PLAYER_ENABLED: bool(player.get("enabled", False)),
            ATTR_TOTAL_SCORE: int(player.get("total_score", 0)),
            ATTR_ROUND_SCORE: int(player.get("current_round_score", 0)),
            ATTR_LAST_ROUND_SCORE: int(player.get("last_round_score", 0)),
            ATTR_CREATED: player.get("created"),
        }

    async def _subscribe_updates(self) -> Callable[[], None]:
        @callback
        def _handle_update() -> None:
            self.async_write_ha_state()

        return async_dispatcher_connect(
            self.hass,
            f"{QUIZ_SIGNAL_UPDATE}_{self.entry_id}_{self.player_id}",
            _handle_update,
        )


class QuizSensorBase(QuizEntityBase, SensorEntity):
    """Base class for player sensors."""

    @property
    def available(self) -> bool:
        return self._player is not None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(await self._subscribe_updates())


class QuizPlayerEnabledBinarySensor(QuizEntityBase, BinarySensorEntity):
    """Binary sensor exposing whether a player is enabled."""

    def __init__(self, hass: HomeAssistant, entry_id: str, player_id: str) -> None:
        super().__init__(hass, entry_id, player_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{player_id}_enabled"
        self.entity_id = f"binary_sensor.{PREFIX_QUIZ}_{player_id}_enabled"
        self._attr_name = "Enabled"

    @property
    def available(self) -> bool:
        return self._player is not None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(await self._subscribe_updates())

    @property
    def is_on(self) -> bool:
        player = self._player or {}
        return bool(player.get("enabled", False))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = self._common_attributes()
        attrs[ATTR_PLAYER_METRIC] = "enabled"
        return attrs


class QuizTotalScoreSensor(QuizSensorBase):
    """Primary total score entity for a player device."""

    def __init__(self, hass: HomeAssistant, entry_id: str, player_id: str) -> None:
        super().__init__(hass, entry_id, player_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{player_id}_total"
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
        attrs = self._common_attributes()
        attrs[ATTR_PLAYER_METRIC] = "total_score"
        return attrs


class QuizRoundScoreSensor(QuizSensorBase):
    """Round score entity for a player device."""

    def __init__(self, hass: HomeAssistant, entry_id: str, player_id: str) -> None:
        super().__init__(hass, entry_id, player_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{player_id}_round"
        self.entity_id = f"sensor.{PREFIX_QUIZ}_{player_id}_round"
        self._attr_name = "Round Score"

    @property
    def native_value(self) -> int | None:
        player = self._player
        if not player:
            return None
        return int(player.get("current_round_score", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = self._common_attributes()
        attrs[ATTR_PLAYER_METRIC] = "round_score"
        return attrs


class QuizLastRoundScoreSensor(QuizSensorBase):
    """Last round score entity for a player device."""

    def __init__(self, hass: HomeAssistant, entry_id: str, player_id: str) -> None:
        super().__init__(hass, entry_id, player_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{player_id}_last_round"
        self.entity_id = f"sensor.{PREFIX_QUIZ}_{player_id}_last_round"
        self._attr_name = "Last Round Score"

    @property
    def native_value(self) -> int | None:
        player = self._player
        if not player:
            return None
        return int(player.get("last_round_score", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = self._common_attributes()
        attrs[ATTR_PLAYER_METRIC] = "last_round_score"
        return attrs


class QuizAliasSensor(QuizSensorBase):
    """Alias entity for a player device."""

    def __init__(self, hass: HomeAssistant, entry_id: str, player_id: str) -> None:
        super().__init__(hass, entry_id, player_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{player_id}_alias"
        self.entity_id = f"sensor.{PREFIX_QUIZ}_{player_id}_alias"
        self._attr_name = "Alias"

    @property
    def native_value(self) -> str | None:
        player = self._player
        if not player:
            return None
        return player.get("alias") or player.get("name") or self.player_id

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = self._common_attributes()
        attrs[ATTR_PLAYER_METRIC] = "alias"
        return attrs