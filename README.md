# Home Assistant Raven Castle Tools

This repository ships a single HACS-installed Home Assistant integration, `raven_castle_jobs`, which is presented in Home Assistant as `Raven Castle Tools`.

That integration exposes both feature areas:

- Raven Castle Jobs
- Raven Castle Quiz

## Installation

### HACS
1. Add this repository as a custom repository in HACS.
2. Install the repository.
3. Restart Home Assistant.
4. Add the `Raven Castle Tools` integration from Settings → Devices & Services.
5. Use the integration's `Configure` action to manage Jobs and Quiz players.

### Manual
1. Copy `custom_components/raven_castle_jobs` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the `Raven Castle Tools` integration from Settings → Devices & Services.

## Raven Castle Jobs

Raven Castle Jobs tracks recurring household jobs as individual devices.

### Device Model

Each job becomes one device with these entities:

- `binary_sensor.rc_jobs_{job_id}`: primary due / not-due state
- `sensor.rc_jobs_{job_id}_last_triggered`
- `sensor.rc_jobs_{job_id}_last_completed`
- `sensor.rc_jobs_{job_id}_next_due`
- `sensor.rc_jobs_{job_id}_created`
- `sensor.rc_jobs_{job_id}_priority`

The primary binary sensor also keeps the scheduling metadata and card-friendly attributes such as `image`, `priority`, `trigger_type`, `cron_expression`, and `days_interval`.

### Managing Jobs

Jobs are added and edited from the integration options flow:

Settings → Devices & Services → Raven Castle Tools → Configure

Each job supports:

- `name`
- `trigger_type`: `schedule` or `frequency`
- `cron_expression`
- `days_interval`
- `image`
- `priority`

### Services

Service domain: `raven_castle_jobs`

- `trigger_job`
- `complete_job`

Example:

```yaml
service: raven_castle_jobs.complete_job
data:
  entity_id: binary_sensor.rc_jobs_trash_day
```

### Jobs Card

The jobs card is auto-registered by the integration.

```yaml
type: custom:rc-jobs-card
job_entities:
  - binary_sensor.rc_jobs_trash_day
  - binary_sensor.rc_jobs_laundry
```

## Raven Castle Quiz

Raven Castle Quiz manages quiz participants as individual devices.

### Device Model

Each player becomes one device with these entities:

- `sensor.rc_quiz_{player_id}`: primary total score entity
- `sensor.rc_quiz_{player_id}_round`
- `sensor.rc_quiz_{player_id}_last_round`
- `sensor.rc_quiz_{player_id}_alias`
- `binary_sensor.rc_quiz_{player_id}_enabled`

The primary total-score entity keeps player metadata in its attributes, including `player_name`, `player_alias`, `player_photo`, `current_round_score`, `last_round_score`, and `enabled`.

### Managing Players

Players are added and edited from the integration options flow:

Settings → Devices & Services → Raven Castle Tools → Configure

Each player supports:

- `name`
- `alias`
- `photo`
- `enabled`

### Services

Service domain: `raven_castle_quiz`

- `add_player`
- `remove_player`
- `enable_player`
- `disable_player`
- `add_points`
- `remove_points`
- `start_new_round`
- `start_new_quiz`
- `reset_quiz`

Example:

```yaml
service: raven_castle_quiz.add_points
data:
  entity_id: sensor.rc_quiz_alice
  points: 5
```

### Quiz Cards

The quiz cards are auto-registered by the integration.

Leaderboard:

```yaml
type: custom:rc-quiz-leaderboard-card
show_disabled: false
max_players: 10
```

Master control:

```yaml
type: custom:rc-quiz-master-card
point_buttons: [5, 10]
compact: false
show_photos: true
```

## Notes

- The HACS repository installs a single integration package because HACS only manages one `custom_components/<domain>` directory per integration repository.
- Both feature areas use local brand assets, so Home Assistant 2026.3 or newer is recommended.
- If the custom cards or logos do not appear immediately after restart, perform a hard browser refresh.

## License

MIT
