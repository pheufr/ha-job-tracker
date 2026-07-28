# Home Assistant Raven House Tools

This repository ships a single HACS-installed Home Assistant integration, `raven_house_tools`, which is presented in Home Assistant as `Raven House Tools`.

That integration exposes both feature areas as separate config entries:

- `RH Jobs`
- `RH Quiz`

## Installation

### HACS
1. Add this repository as a custom repository in HACS.
2. Install the repository.
3. Restart Home Assistant.
4. Add the `Raven House Tools` integration twice from Settings -> Devices & Services.
5. Choose `RH Jobs` for job management and `RH Quiz` for quiz management.

### Manual
1. Copy `custom_components/raven_house_tools` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the `Raven House Tools` integration from Settings -> Devices & Services for each feature you want.

## Raven House Jobs

The `RH Jobs` entry tracks recurring household jobs as individual devices.

### Device Model

Each job becomes one device with these entities:

- `binary_sensor.rh_jobs_{job_id}`: primary due / not-due state
- `switch.rh_jobs_{job_id}_manual_due`: trigger/dismiss state manually
- `text.rh_jobs_{job_id}_name`: rename the job
- `sensor.rh_jobs_{job_id}_last_triggered`
- `sensor.rh_jobs_{job_id}_last_completed`
- `sensor.rh_jobs_{job_id}_next_due`
- `sensor.rh_jobs_{job_id}_created`
- `sensor.rh_jobs_{job_id}_priority`

The primary binary sensor also keeps the scheduling metadata and card-friendly attributes such as `image`, `priority`, `trigger_type`, `cron_expression`, and `days_interval`.

### Managing Jobs

Jobs can be managed from the job device page using control entities.

Jobs can also be created via the `raven_house_tools.add_job` service.

To edit or delete an existing job, open the RH Jobs integration options and choose Manage Jobs (Edit/Delete).

Each job supports:

- `name`
- `trigger_type`: `schedule`, `frequency`, or `manual`
- `cron_expression`
- `days_interval`
- `image` (supports media picker/upload in flows and services)
- `priority`

### Services

Service domain: `raven_house_tools`

- `trigger_job`
- `complete_job`
- `dismiss_job`
- `rename_job`
- `update_job_image`
- `add_job`

Example:

```yaml
service: raven_house_tools.complete_job
data:
  entity_id: binary_sensor.rh_jobs_trash_day
```

Set/update job image without manually typing a URL:

```yaml
service: raven_house_tools.update_job_image
data:
  entity_id: binary_sensor.rh_jobs_trash_day
  image: /media/local/jobs/trash.png
```

Use the Actions/Services UI target picker for the job entity and image picker for `image`.

How to upload a new image for selection:

1. In Home Assistant, open Media -> My media.
2. Choose or create a folder (for example `jobs`).
3. Click Upload and upload the image file.
4. Return to the action/service form and pick that image from the media browser.

If you do not see Create folder or Upload in My media:

1. Verify the Local Media integration is installed and loaded.
2. Place files directly in your Home Assistant config at `/config/media/jobs/` (or another folder under `/config/media/`).
3. Restart Home Assistant, then reopen the media picker.
4. Select the image from the media browser, or provide `/media/local/jobs/<filename>` as the value.

### Example Automations

Calendar-driven trigger (example: `calendar.bins` and job `96566d0a`):

```yaml
alias: RH Jobs - Trigger from bins calendar
mode: single
triggers:
  - trigger: calendar
    entity_id: calendar.bins
    event: start
    offset: "-24:00:00"
conditions:
  - condition: template
    value_template: >
      {{ trigger.calendar_event.summary | lower == states('text.rh_jobs_96566d0a_name') | lower }}
  - condition: template
    value_template: >
      {% set due_window_hours = 24 %}
      {% set last_completed = states('sensor.rh_jobs_96566d0a_last_completed') %}
      {% set last_completed_dt = as_datetime(last_completed, default=none) %}
      {{ last_completed in ['unknown', 'unavailable', '']
         or (last_completed_dt is not none and last_completed_dt < (now() - timedelta(hours=due_window_hours))) }}
actions:
  - action: button.press
    target:
      entity_id: button.rh_jobs_96566d0a_trigger
```

Auto-dismiss/complete from a sensor state change:

```yaml
alias: RH Jobs - Auto complete from front door
mode: single
triggers:
  - trigger: state
    entity_id: binary_sensor.front_door_opening
    to: "on" # "on" is shown as Open for opening binary_sensors
actions:
  - action: button.press
    target:
      entity_id: button.rh_jobs_96566d0a_complete
```

`binary_sensor` entities use `on`/`off` states in automations (`on` is shown as `Open` for `opening` device class sensors).

### Jobs Card

The jobs card is auto-registered by the integration.

```yaml
type: custom:rh-jobs-card
orientation: vertical
job_entities:
  - binary_sensor.rh_jobs_trash_day
  - binary_sensor.rh_jobs_laundry
```

Jobs card layout options:

- `orientation: vertical` (default) stacks due jobs top-to-bottom.
- `orientation: horizontal` places jobs in a horizontal wrapping layout.

## Raven House Quiz

The `RH Quiz` entry manages quiz participants as individual devices.

### Device Model

Each player becomes one device with these entities:

- `sensor.rh_quiz_{player_id}`: primary total score entity
- `sensor.rh_quiz_{player_id}_round`
- `sensor.rh_quiz_{player_id}_last_round`
- `sensor.rh_quiz_{player_id}_alias`
- `binary_sensor.rh_quiz_{player_id}_enabled`
- `switch.rh_quiz_{player_id}_enabled`: enable/disable from device view
- `button.rh_quiz_{player_id}_reset_score`: reset one participant score
- `text.rh_quiz_{player_id}_name`: rename participant
- `text.rh_quiz_{player_id}_alias`: update alias
- `text.rh_quiz_{player_id}_photo`: update image path

The primary total-score entity keeps player metadata in its attributes, including `player_name`, `player_alias`, `player_photo`, `current_round_score`, `last_round_score`, and `enabled`.

### Managing Players

Players can be managed from each participant's device page using control entities.

Players can also be created via the `raven_house_tools.add_player` service.

Each player supports:

- `name`
- `alias`
- `photo` (supports media picker/upload in flows and services)
- `enabled`

### Services

Service domain: `raven_house_tools`

- `add_player`
- `remove_player`
- `enable_player`
- `disable_player`
- `rename_player`
- `update_player_alias`
- `update_player_photo`
- `reset_player_score`
- `add_points`
- `remove_points`
- `start_new_round`
- `start_new_quiz`
- `reset_quiz`

Example:

```yaml
service: raven_house_tools.add_points
data:
  entity_id: sensor.rh_quiz_alice
  points: 5
```

Update player photo without manually typing a URL:

```yaml
service: raven_house_tools.update_player_photo
data:
  entity_id: sensor.rh_quiz_alice
  photo: /media/local/players/alice.png
```

Use the Actions/Services UI target picker for the player entity and image picker for `photo`.

How to upload a new player photo:

1. In Home Assistant, open Media -> My media.
2. Choose or create a folder (for example `players`).
3. Click Upload and upload the image file.
4. Return to the action/service form and pick that image from the media browser.

If you do not see Create folder or Upload in My media:

1. Verify the Local Media integration is installed and loaded.
2. Place files directly in your Home Assistant config at `/config/media/players/` (or another folder under `/config/media/`).
3. Restart Home Assistant, then reopen the media picker.
4. Select the image from the media browser, or provide `/media/local/players/<filename>` as the value.

### Quiz Cards

The quiz cards are auto-registered by the integration.

Leaderboard:

```yaml
type: custom:rh-quiz-leaderboard-card
show_disabled: false
max_players: 10
```

Master control:

```yaml
type: custom:rh-quiz-master-card
point_buttons: [5, 10]
compact: false
show_photos: true
```

## Raven House Soundboard

The Soundboard feature adds a custom card and services for low-latency short audio effects to media players.

### Services

Service domain: `raven_house_tools`

- `soundboard_set_target`
- `soundboard_set_mode`
- `soundboard_connect`
- `soundboard_disconnect`
- `soundboard_play_clip`

Recommended flow:

1. Set or select a target media player.
2. Connect once (optionally with a `dead_air_media` clip).
3. Trigger clips repeatedly.
4. Disconnect when done.

### Soundboard Card

The soundboard card is auto-registered by the integration.

```yaml
type: custom:rh-soundboard-card
title: RH Soundboard
columns: 5
target: media_player.living_room_speaker
allow_target_switch: true
dead_air_media: media-source://media_source/local/soundboard/dead_air.mp3
clips:
  - id: air_horn
    label: Air Horn
    icon: mdi:bullhorn
    type: sfx
    fg_color: "#ffffff"
    bg_color: "#c0392b"
    media: media-source://media_source/local/sfx/air_horn.mp3
  - id: applause
    label: Applause
    icon: mdi:hand-clap
    type: crowd
    fg_color: "#1f2a44"
    bg_color: "#f9d976"
    media: media-source://media_source/local/sfx/applause.mp3
default_mode: connected
show_mode_selector: true
```

Clip fields:

- `id`: stable identifier for the button
- `label`: button text
- `icon`: Material Design icon
- `type`: clip category/label shown on the button (for example `sfx`, `crowd`, `voice`)
- `media`: media-source or URL/path to an audio file
- `fg_color`: optional per-button foreground/text color
- `bg_color`: optional per-button background color

Optional card fields:

- `default_mode`: `connected` (default) or `direct`
- `show_mode_selector`: set `false` to hide the in-card mode select

Runtime status sensor:

- `sensor.rh_soundboard_session`

The card reads this sensor to reflect live connection state, pending requests, and per-target playback mode.

## Notes

- The HACS repository installs a single integration package because HACS only manages one `custom_components/<domain>` directory per integration repository.
- Legacy installs created before the split keep working as a combined entry, but new installs should add separate `RH Jobs` and `RH Quiz` entries.
- Both feature areas use local brand assets, so Home Assistant 2026.3 or newer is recommended.
- If the custom cards or logos do not appear immediately after restart, perform a hard browser refresh.

## License

MIT
