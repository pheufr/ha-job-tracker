# Home Assistant Job Manager

A Home Assistant custom integration that allows you to manage recurring jobs/tasks. Each job is exposed as a binary sensor device that automatically tracks when it's due based on schedules or frequencies.

## Features

- **Schedule-based triggers**: Use cron expressions (1st of month, last Tuesday, etc.)
- **Frequency-based triggers**: Mark as due every N days since last completion
- **Manual triggers**: Use the `trigger_job` action to manually mark a job as due
- **Manual completion**: Use the `complete_job` action to mark a job as completed
- **Automations**: Integrate with Home Assistant automations to take actions when jobs become due
- **Binary sensor devices**: Each job is exposed as a binary sensor (on = due, off = not due)

## Installation

1. Clone this repository into your `custom_components` folder:
   ```bash
   git clone https://github.com/pheufr/ha-job-tracker.git custom_components/job_manager
   ```

2. Restart Home Assistant

3. Add the integration via Settings → Devices & Services → Create Integration

## Usage

### Creating Jobs

Jobs are created and managed through the Home Assistant UI or via YAML configuration.

### Service: `trigger_job`

Manually trigger a job to mark it as due:

```yaml
service: job_manager.trigger_job
data:
  entity_id: binary_sensor.job_manager_trash_day
```

### Service: `complete_job`

Mark a job as completed:

```yaml
service: job_manager.complete_job
data:
  entity_id: binary_sensor.job_manager_trash_day
```

### Example Automation

Trigger a notification when a job becomes due:

```yaml
automation:
  - alias: "Notify when job is due"
    trigger:
      - platform: state
        entity_id: binary_sensor.job_manager_trash_day
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
      - service: job_manager.complete_job
        data:
          entity_id: binary_sensor.job_manager_evening_routine
```

## Job Configuration

Each job has the following properties:

- **name**: Display name of the job
- **trigger_type**: Either `schedule` or `frequency`
- **cron_expression** (for schedule type): Cron expression for when the job is due
- **days_interval** (for frequency type): Number of days between job occurrences
- **last_completed**: Timestamp of when the job was last completed
- **last_triggered**: Timestamp of when the job was last triggered

### Trigger Types

#### Schedule (Cron-based)
Use standard cron expressions:
- `0 9 * * 1` - Every Monday at 9 AM
- `0 0 1 * *` - First day of every month at midnight
- `0 0 * * 2` - Every Tuesday at midnight (use for "last Tuesday", update cron as needed)

#### Frequency (Interval-based)
Specify the number of days:
- `30` - Every 30 days since last completion
- `7` - Every 7 days (weekly)
- `1` - Every day

## State Attributes

Each job binary sensor includes the following attributes:

- `trigger_type`: The type of trigger (schedule or frequency)
- `cron_expression`: The cron expression (for schedule type)
- `days_interval`: The interval in days (for frequency type)
- `last_completed`: ISO timestamp of last completion
- `last_triggered`: ISO timestamp of last trigger
- `created`: ISO timestamp when the job was created

## License

MIT
