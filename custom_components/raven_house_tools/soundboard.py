"""Soundboard services for Raven House Tools."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from dataclasses import field
import logging
import time
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.util.dt import utcnow

from .const import (
    DOMAIN,
    SERVICE_SOUNDBOARD_CONNECT,
    SERVICE_SOUNDBOARD_DISCONNECT,
    SERVICE_SOUNDBOARD_PLAY_CLIP,
    SERVICE_SOUNDBOARD_SET_MODE,
    SERVICE_SOUNDBOARD_SET_TARGET,
)

_LOGGER = logging.getLogger(__name__)

SOUNDBOARD_STATE_ENTITY_ID = "sensor.rh_soundboard_session"
MODE_CONNECTED = "connected"
MODE_DIRECT = "direct"


MEDIA_SELECTOR_SCHEMA = vol.Schema(
    {
        vol.Required("media_content_id"): cv.string,
        vol.Optional("media_content_type"): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)


def _normalize_media_value(value: Any) -> str:
    """Normalize media selector output into a storable path/URL."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("url", "entity_picture", "path"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate.strip()

        metadata = value.get("metadata")
        if isinstance(metadata, dict):
            thumbnail = metadata.get("thumbnail")
            if isinstance(thumbnail, str):
                return thumbnail.strip()

        media_content_id = value.get("media_content_id")
        if isinstance(media_content_id, str):
            return media_content_id.strip()
    return ""


@dataclass
class SoundboardSession:
    """In-memory soundboard playback session state."""

    target_entity_id: str = ""
    dead_air_media: str = ""
    connected: bool = False
    connected_at: str = ""
    last_clip: str = ""
    last_triggered: str = ""
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    pending_requests: int = 0
    min_trigger_gap_ms: int = 120
    max_pending_requests: int = 2
    rejected_rapid: int = 0
    rejected_overflow: int = 0
    last_trigger_monotonic: float = 0.0
    mode_by_target: dict[str, str] = field(default_factory=dict)


def _session(hass: HomeAssistant) -> SoundboardSession:
    """Get the global soundboard session object."""
    data = hass.data.setdefault(DOMAIN, {})
    existing = data.get("soundboard_session")
    if isinstance(existing, SoundboardSession):
        return existing
    created = SoundboardSession()
    data["soundboard_session"] = created
    return created


def _publish_state(hass: HomeAssistant, session: SoundboardSession) -> None:
    """Publish current soundboard state as a lightweight sensor."""
    hass.states.async_set(
        SOUNDBOARD_STATE_ENTITY_ID,
        "connected" if session.connected else "disconnected",
        {
            "active_target": session.target_entity_id,
            "dead_air_media": session.dead_air_media,
            "connected": session.connected,
            "connected_at": session.connected_at,
            "last_clip": session.last_clip,
            "last_triggered": session.last_triggered,
            "pending_requests": session.pending_requests,
            "rejected_rapid": session.rejected_rapid,
            "rejected_overflow": session.rejected_overflow,
            "min_trigger_gap_ms": session.min_trigger_gap_ms,
            "max_pending_requests": session.max_pending_requests,
            "mode_by_target": dict(session.mode_by_target),
            "friendly_name": "RH Soundboard Session",
        },
    )


def _target_mode(session: SoundboardSession, entity_id: str) -> str:
    mode = session.mode_by_target.get(entity_id, MODE_CONNECTED)
    if mode not in (MODE_CONNECTED, MODE_DIRECT):
        return MODE_CONNECTED
    return mode


async def _play_media(
    hass: HomeAssistant,
    entity_id: str,
    media: str,
    *,
    enqueue: str | None = None,
) -> None:
    """Play media on target entity."""
    payload: dict[str, Any] = {
        "entity_id": entity_id,
        "media_content_id": media,
        "media_content_type": "music",
        "announce": False,
    }
    if enqueue:
        payload["enqueue"] = enqueue
    await hass.services.async_call("media_player", "play_media", payload, blocking=True)


async def _next_track(hass: HomeAssistant, entity_id: str) -> None:
    """Skip to next track on target entity."""
    await hass.services.async_call(
        "media_player",
        "media_next_track",
        {"entity_id": entity_id},
        blocking=True,
    )


async def _stop(hass: HomeAssistant, entity_id: str) -> None:
    """Stop playback on target entity."""
    await hass.services.async_call(
        "media_player",
        "media_stop",
        {"entity_id": entity_id},
        blocking=True,
    )


async def async_setup_soundboard_services(hass: HomeAssistant) -> None:
    """Register Raven House soundboard services."""

    async def _set_target(call: ServiceCall) -> None:
        session = _session(hass)
        target = str(call.data.get("entity_id", "")).strip()
        if not target:
            return
        session.target_entity_id = target
        _publish_state(hass, session)

    async def _set_mode(call: ServiceCall) -> None:
        session = _session(hass)
        target = str(call.data.get("entity_id", "")).strip()
        mode = str(call.data.get("mode", MODE_CONNECTED)).strip().lower()
        if not target:
            return
        if mode not in (MODE_CONNECTED, MODE_DIRECT):
            mode = MODE_CONNECTED
        session.mode_by_target[target] = mode
        _publish_state(hass, session)

    async def _connect(call: ServiceCall) -> None:
        session = _session(hass)
        target = str(call.data.get("entity_id", "")).strip() or session.target_entity_id
        if not target:
            _LOGGER.warning("soundboard_connect called without a media_player target")
            return

        dead_air = _normalize_media_value(call.data.get("dead_air_media", ""))
        if dead_air:
            session.dead_air_media = dead_air
        if session.dead_air_media:
            await _play_media(hass, target, session.dead_air_media, enqueue="replace")

        session.target_entity_id = target
        session.connected = True
        session.connected_at = utcnow().isoformat()
        _publish_state(hass, session)

    async def _disconnect(call: ServiceCall) -> None:
        session = _session(hass)
        target = str(call.data.get("entity_id", "")).strip() or session.target_entity_id
        if target:
            await _stop(hass, target)
        session.connected = False
        _publish_state(hass, session)

    async def _play_clip(call: ServiceCall) -> None:
        session = _session(hass)
        target = str(call.data.get("entity_id", "")).strip() or session.target_entity_id
        if not target:
            _LOGGER.warning("soundboard_play_clip called without a media_player target")
            return

        media = _normalize_media_value(call.data.get("media", ""))
        if not media:
            _LOGGER.warning("soundboard_play_clip called without media")
            return

        requested_mode = str(call.data.get("mode", "")).strip().lower()
        if requested_mode not in (MODE_CONNECTED, MODE_DIRECT):
            requested_mode = _target_mode(session, target)
        connected_mode = bool(call.data.get("connected", requested_mode == MODE_CONNECTED))
        dead_air_override = _normalize_media_value(call.data.get("dead_air_media", ""))
        if dead_air_override:
            session.dead_air_media = dead_air_override

        if session.pending_requests >= session.max_pending_requests:
            session.rejected_overflow += 1
            _publish_state(hass, session)
            return

        session.pending_requests += 1
        _publish_state(hass, session)
        try:
            async with session.lock:
                now = time.monotonic()
                min_gap_s = session.min_trigger_gap_ms / 1000.0
                if session.last_trigger_monotonic and (now - session.last_trigger_monotonic) < min_gap_s:
                    session.rejected_rapid += 1
                    _publish_state(hass, session)
                    return

                if connected_mode:
                    if session.target_entity_id != target:
                        session.target_entity_id = target
                    if not session.connected and session.dead_air_media:
                        await _play_media(hass, target, session.dead_air_media, enqueue="replace")
                        session.connected = True
                        session.connected_at = utcnow().isoformat()

                    if session.connected and session.dead_air_media:
                        # Queue clip and dead-air then advance once to keep a warm session.
                        await _play_media(hass, target, media, enqueue="next")
                        await _play_media(hass, target, session.dead_air_media, enqueue="add")
                        await _next_track(hass, target)
                    else:
                        await _play_media(hass, target, media, enqueue="play")
                else:
                    await _play_media(hass, target, media, enqueue="replace")

                session.target_entity_id = target
                session.mode_by_target[target] = MODE_CONNECTED if connected_mode else MODE_DIRECT
                session.last_clip = media
                session.last_triggered = utcnow().isoformat()
                session.last_trigger_monotonic = now
                _publish_state(hass, session)
        finally:
            session.pending_requests = max(0, session.pending_requests - 1)
            _publish_state(hass, session)

    target_schema = vol.Schema({vol.Required("entity_id"): cv.entity_id})
    optional_target_schema = vol.Schema({vol.Optional("entity_id"): cv.entity_id})
    connect_schema = vol.Schema(
        {
            vol.Required("entity_id"): cv.entity_id,
            vol.Optional("dead_air_media"): vol.Any(cv.string, MEDIA_SELECTOR_SCHEMA),
        }
    )
    clip_schema = vol.Schema(
        {
            vol.Optional("entity_id"): cv.entity_id,
            vol.Required("media"): vol.Any(cv.string, MEDIA_SELECTOR_SCHEMA),
            vol.Optional("connected", default=False): cv.boolean,
            vol.Optional("mode"): vol.In([MODE_CONNECTED, MODE_DIRECT]),
            vol.Optional("dead_air_media"): vol.Any(cv.string, MEDIA_SELECTOR_SCHEMA),
        }
    )
    mode_schema = vol.Schema(
        {
            vol.Required("entity_id"): cv.entity_id,
            vol.Optional("mode", default=MODE_CONNECTED): vol.In([MODE_CONNECTED, MODE_DIRECT]),
        }
    )

    _publish_state(hass, _session(hass))

    if not hass.services.has_service(DOMAIN, SERVICE_SOUNDBOARD_SET_TARGET):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SOUNDBOARD_SET_TARGET,
            _set_target,
            schema=target_schema,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SOUNDBOARD_SET_MODE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SOUNDBOARD_SET_MODE,
            _set_mode,
            schema=mode_schema,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SOUNDBOARD_CONNECT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SOUNDBOARD_CONNECT,
            _connect,
            schema=connect_schema,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SOUNDBOARD_DISCONNECT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SOUNDBOARD_DISCONNECT,
            _disconnect,
            schema=optional_target_schema,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SOUNDBOARD_PLAY_CLIP):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SOUNDBOARD_PLAY_CLIP,
            _play_clip,
            schema=clip_schema,
        )


async def async_unload_soundboard(hass: HomeAssistant) -> None:
    """Best-effort cleanup for soundboard runtime state."""
    domain_data = hass.data.get(DOMAIN, {})
    session = domain_data.get("soundboard_session")
    if not isinstance(session, SoundboardSession):
        return
    if session.connected and session.target_entity_id:
        try:
            await _stop(hass, session.target_entity_id)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Unable to stop soundboard target on unload", exc_info=True)
    session.connected = False
    _publish_state(hass, session)
