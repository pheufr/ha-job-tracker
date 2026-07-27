# Soundboard Implementation Handoff

Date: 2026-07-27
Repository: ha-raven-castle-tools
Integration domain: raven_house_tools

## Goal
Build a low-latency soundboard feature for Home Assistant that:
- Targets selectable media_player entities (Chromecast/generic supported).
- Uses a custom Lovelace card with configurable clip buttons and columns.
- Supports connect/disconnect behavior to reduce repeated connection chimes.
- Prioritizes fast trigger-to-audio response.

## Target Architecture
1. Backend service layer in integration
- Services: soundboard_set_target, soundboard_connect, soundboard_disconnect, soundboard_play_clip.
- Optional advanced service: soundboard_set_mode (connected/direct).
- Session state held in memory and exposed via sensor.rh_soundboard_session.

2. Frontend custom card
- Card type: custom:rh-soundboard-card.
- Configurable clips list, icons, labels, columns, default target, optional target switch.
- Connect/disconnect control plus clip trigger grid.
- Optional playback mode selector (connected/direct) when supported.

3. Playback strategy
- Connected mode: attempt queue-based warm-session flow for reduced chime/reconnect overhead.
- Direct mode: fallback immediate play for compatibility.
- Graceful fallback when queue/enqueue features are not accepted by media player schema.

## Implemented So Far
### Backend
- Added soundboard backend module:
  - custom_components/raven_house_tools/soundboard.py
- Added service constants:
  - custom_components/raven_house_tools/const.py
- Registered service setup and unload wiring:
  - custom_components/raven_house_tools/__init__.py
- Added service metadata:
  - custom_components/raven_house_tools/services.yaml
- Added session status publishing:
  - sensor.rh_soundboard_session state/attributes from backend runtime.
- Added basic guardrails:
  - Request lock.
  - Pending request cap.
  - Minimum trigger gap.
  - Rejection counters for rapid/overflow conditions.
- Added queue compatibility fallback:
  - If enqueue-style play fails with enqueue_announce conflict, retry as direct play.

### Frontend
- Added card module:
  - custom_components/raven_house_tools/www/rh-soundboard-card.js
- Registered new card asset:
  - custom_components/raven_house_tools/frontend.py
- Card supports:
  - Clip grid, connect/disconnect button, optional target selector.
  - Optional mode selector.
  - Runtime status display from sensor.rh_soundboard_session.
- Added service capability checks in card:
  - Avoid calling missing soundboard_set_mode service.
  - Avoid sending unsupported mode field to soundboard_play_clip.

### Documentation
- Added soundboard section with config example and options:
  - README.md

## Key Pitfalls Encountered and Fixes
1. Lovelace config immutability
- Symptom: "Cannot add property clips, object is not extensible"
- Cause: Card mutated the incoming config object.
- Fix: Clone config in setConfig and normalize defaults on clone.

2. Service mismatch between frontend and backend
- Symptom: "Action raven_house_tools.soundboard_set_mode not found"
- Symptom: "extra keys not allowed @ data['mode']"
- Cause: Frontend used newer fields/services while runtime backend schema was older/not reloaded.
- Fix: Frontend capability detection before calling services/sending fields.

3. enqueue_announce schema conflict
- Symptom: "two or more values in the same group of exclusion 'enqueue_announce'"
- Cause: Some play_media payload combinations conflict with strict service validation.
- Fixes:
  - Do not send announce when enqueue is present.
  - Add enqueue conflict fallback to direct play when needed.

## Current Known Risks
- Media player integrations differ in queue behavior; connected mode may still behave inconsistently across targets.
- Queue chaining with dead-air may be less effective on players that do not support enqueue semantics.
- In some environments, full Home Assistant restart is required after backend changes for schemas/services to refresh.

## Resume Checklist (Next Session)
1. Verify runtime service registrations in Home Assistant Developer Tools:
- raven_house_tools.soundboard_connect
- raven_house_tools.soundboard_disconnect
- raven_house_tools.soundboard_play_clip
- raven_house_tools.soundboard_set_target
- raven_house_tools.soundboard_set_mode (optional advanced)

2. Validate connected mode on primary Chromecast target:
- Connect once.
- Trigger multiple clips rapidly.
- Confirm no service validation errors and acceptable latency.

3. Capture behavior by player type:
- Works in connected mode.
- Requires direct fallback.
- Chime/no-chime observed.

4. Optional next improvements:
- Add explicit UI capability badge (advanced mode available/unavailable).
- Add per-target persisted preferences for mode and dead-air clip.
- Add adaptive retry chain for next-track/queue handoff failures.

## Quick Card Example
```yaml
type: custom:rh-soundboard-card
title: RH Soundboard
columns: 5
target: media_player.living_room_speaker
allow_target_switch: true
dead_air_media: media-source://media_source/local/soundboard/dead_air.mp3
default_mode: connected
show_mode_selector: true
clips:
  - id: air_horn
    label: Air Horn
    icon: mdi:bullhorn
    media: media-source://media_source/local/sfx/air_horn.mp3
  - id: applause
    label: Applause
    icon: mdi:hand-clap
    media: media-source://media_source/local/sfx/applause.mp3
```

## Notes for Handoff
- If errors reference missing service or invalid data keys, first suspect stale backend registration; restart HA before deeper debugging.
- Keep frontend backward-compatible with service schemas to reduce operator friction during iterative rollout.
