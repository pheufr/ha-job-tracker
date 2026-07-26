# Home Assistant Raven Castle Tools

A multi-feature Home Assistant custom integration providing tools for home automation.

## Features

### RC Jobs ✅
Track and manage recurring jobs/tasks with customizable schedules or frequencies. Each job is exposed as a binary sensor that automatically tracks when it is due.

**Entity naming**: `binary_sensor.rc_jobs_{job_id}`

### RC Quiz 🔜
Interactive quiz system with player tracking (coming soon).

**Entity naming**: `sensor.rc_quiz_{player_id}`

## Installation

### HACS (recommended)
1. Add this repository to HACS as a custom repository
2. Install "Raven Castle" from HACS
3. Restart Home Assistant
4. Add the integration via Settings → Devices & Services → Add Integration → Raven Castle

### Manual
1. Copy `custom_components/raven_castle/` to your Home Assistant `custom_components` folder
2. Restart Home Assistant
3. Add the integration via Settings → Devices & Services → Add Integration → Raven Castle

### Migration from Job Manager
If you previously used the `job_manager` integration, the Raven Castle integration will automatically migrate your data:
- Entity IDs will be updated: `binary_sensor.job_manager_*` → `binary_sensor.rc_jobs_*`
- All job data (schedules, last completed, etc.) is preserved
- **Note**: Update any automations or scripts that reference the old entity IDs

## RC Jobs

### Creating Jobs

Jobs are created and managed through the Home Assistant UI via the integration's options flow.

Each job supports:
- **name**: Display name
- **trigger_type**: `schedule` or `frequency`
- **cron_expression**: For schedule type (e.g., `0 0 1 * *` for 1st of month)
- **days_interval**: For frequency type (e.g., `30` for every 30 days)
- **image**: URL to an image to display in the picture card
- **priority**: Integer priority level (higher = shown first in picture card)

### Services

#### `raven_castle.trigger_job`

Manually trigger a job to mark it as due:

```yaml
service: raven_castle_tools.trigger_job
data:
  entity_id: binary_sensor.rc_jobs_trash_day
```

#### `raven_castle.complete_job`

Mark a job as completed:

```yaml
service: raven_castle_tools.complete_job
data:
  entity_id: binary_sensor.rc_jobs_trash_day
```

### RC Jobs Card

Add a custom Lovelace card to display job images. First, add the resource in Lovelace settings:

```yaml
type: custom:rc-jobs-card
job_entities:
  - binary_sensor.rc_jobs_trash_day
  - binary_sensor.rc_jobs_laundry
  - binary_sensor.rc_jobs_yard_work
```

**Features:**
- Shows only due jobs with assigned images
- Sorted by priority (highest first)
- Click on an image to complete the job
- No borders or background, just images
- Hover tooltip shows job name and priority

### Example Automation

Trigger a notification when a job becomes due:

```yaml
automation:
  - alias: "Notify when job is due"
    trigger:
      - platform: state
        entity_id: binary_sensor.rc_jobs_trash_day
        to: "on"
    action:
      - service: notify.notify
        data:
          message: "Trash day is due!"
```

Automatically complete a job after an action:

```yaml
automation:
  - alias: "Complete job after action"
    trigger:
      - platform: time
        at: "20:00:00"
    action:
      - service: raven_castle_tools.complete_job
        data:
          entity_id: binary_sensor.rc_jobs_evening_routine
```

### Job Trigger Types

#### Schedule (Cron-based)
Use standard cron expressions:
- `0 9 * * 1` - Every Monday at 9 AM
- `0 0 1 * *` - First day of every month at midnight
- `0 0 * * 2` - Every Tuesday at midnight

#### Frequency (Interval-based)
Specify the number of days:
- `30` - Every 30 days since last completion
- `7` - Every 7 days (weekly)
- `1` - Every day

### State Attributes

Each RC Jobs binary sensor includes the following attributes:

- `trigger_type`: The type of trigger (`schedule` or `frequency`)
- `cron_expression`: The cron expression (for schedule type)
- `days_interval`: The interval in days (for frequency type)
- `image`: URL to the job's image
- `priority`: Priority level for sorting
- `last_completed`: ISO timestamp of last completion
- `last_triggered`: ISO timestamp of last trigger
- `created`: ISO timestamp when the job was created

## License

MIT


## RC Quiz

RC Quiz adds player-based score tracking with entities like `sensor.rc_quiz_<player_id>` and services such as `add_player`, `add_points`, `start_new_round`, and `start_new_quiz` under the `raven_castle_tools` domain.

Two custom cards are included in `custom_components/raven_castle_tools/www`:
- `rc-quiz-leaderboard-card.js` for public score display
- `rc-quiz-master-card.js` for quiz control actions
