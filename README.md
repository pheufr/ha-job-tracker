# Home Assistant Raven Castle Tools

A multi-feature Home Assistant custom integration providing tools for home automation.

## Features

### RC Jobs ✅
Track and manage recurring jobs/tasks with customizable schedules or frequencies. Each job is exposed as a binary sensor that automatically tracks when it is due.

**Entity naming**: `binary_sensor.rc_jobs_{job_id}`

### RC Quiz ✅
Interactive quiz system with player tracking, scores per round, and custom Lovelace cards.

**Entity naming**: `sensor.rc_quiz_{player_id}`

## Installation

### HACS (recommended)
1. Add this repository to HACS as a custom repository
2. Install "Raven Castle Tools" from HACS
3. Restart Home Assistant
4. Add the integration via Settings → Devices & Services → Add Integration → Raven Castle Tools

### Manual
1. Copy `custom_components/raven_castle_tools/` to your Home Assistant `custom_components` folder
2. Restart Home Assistant
3. Add the integration via Settings → Devices & Services → Add Integration → Raven Castle Tools

### Migration from Job Manager
If you previously used the `job_manager` integration, Raven Castle Tools will automatically migrate your data:
- Entity IDs will be updated: `binary_sensor.job_manager_*` → `binary_sensor.rc_jobs_*`
- All job data (schedules, last completed, etc.) is preserved
- **Note**: Update any automations or scripts that reference the old entity IDs

## RC Jobs

### Creating Jobs

Jobs are created and managed through the Home Assistant UI via the integration's options flow (Settings → Devices & Services → Raven Castle Tools → Configure → Manage RC Jobs).

Each job supports:
- **name**: Display name
- **trigger_type**: `schedule` or `frequency`
- **cron_expression**: For schedule type (e.g., `0 0 1 * *` for 1st of month)
- **days_interval**: For frequency type (e.g., `30` for every 30 days)
- **image**: URL to an image to display in the picture card
- **priority**: Integer priority level (higher = shown first in picture card)

### Services

#### `raven_castle_tools.trigger_job`

Manually trigger a job to mark it as due:

```yaml
service: raven_castle_tools.trigger_job
data:
  entity_id: binary_sensor.rc_jobs_trash_day
```

#### `raven_castle_tools.complete_job`

Mark a job as completed:

```yaml
service: raven_castle_tools.complete_job
data:
  entity_id: binary_sensor.rc_jobs_trash_day
```

### RC Jobs Card

Add a custom Lovelace card to display job images. First register the resource in Lovelace settings:
`/local/raven_castle_tools/rc-jobs-card.js`

Then use it in your dashboard:

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
- Hover tooltip shows job name and priority

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

## RC Quiz

RC Quiz adds player-based score tracking for quiz games.

### Managing Players

Players are managed through the integration's options flow (Settings → Devices & Services → Raven Castle Tools → Configure → Manage RC Quiz).

Each player has:
- **name**: Full name
- **alias**: Display name shown on leaderboard
- **photo**: URL or local path to player photo
- **enabled**: Whether the player is active in the current quiz

### Entities

Per player, two sensors are created:
- `sensor.rc_quiz_{player_id}` - Total score (with all player attributes)
- `sensor.rc_quiz_{player_id}_round` - Current round score

### Services

All services are under the `raven_castle_tools` domain:

| Service | Description |
|---------|-------------|
| `add_player` | Add a new quiz player |
| `remove_player` | Remove a player permanently |
| `enable_player` | Enable a player for the current quiz |
| `disable_player` | Disable a player for the current quiz |
| `add_points` | Add points to a player's round score |
| `remove_points` | Remove points from a player's round score |
| `start_new_round` | Finalise current round scores into totals and reset round |
| `start_new_quiz` | Reset all scores to zero |
| `reset_quiz` | Reset all scores and disable all players |

### RC Quiz Cards

Two custom Lovelace cards are included. Register these resources in Lovelace settings:
- `/local/raven_castle_tools/rc-quiz-leaderboard-card.js`
- `/local/raven_castle_tools/rc-quiz-master-card.js`

#### Leaderboard Card

```yaml
type: custom:rc-quiz-leaderboard-card
show_disabled: false
max_players: 10
```

Shows players ordered by total score with medals (🥇🥈🥉), photos, alias, and scores.

#### Quiz Master Card

```yaml
type: custom:rc-quiz-master-card
point_buttons: [5, 10]
compact: false
show_photos: true
```

Shows all players alphabetically with controls to add/remove points, enable/disable players, and start new rounds.

## License

MIT
