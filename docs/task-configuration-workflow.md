# Task Configuration Workflow

Use this workflow when changing task metadata, execution settings, or strategy parameters after a task has been created.

## Metadata Edits

Task name and description are metadata. They can be edited whenever the task is not actively owned by a worker.

Worker-owned statuses are `starting`, `running`, `idle`, `draining`, and `stopping`.

## Strategy Parameter Edits

To apply new strategy parameters to an existing execution:

1. Stop the trading task, or pause/stop the backtest task.
2. Edit the strategy configuration.
3. Resume the task.
4. Verify the effective config in task logs and execution history.

Resume keeps the same `execution_id` and creates a new worker segment. Execution history shows the segment number and config revision count.

## Restart Required

Some edits change the execution shape and require a restart instead of resume. Examples:

- instrument
- pip size
- data source
- date range
- initial balance
- account or hedging mode
- strategy type
- decreasing snowball `r_max`

When resume is blocked, the API returns a structured error with `error_code`, `restart_required`, `blocked_fields`, and `safe_fields`.

## Verification

Use these places to verify applied values:

- Task logs: filter by `config.audit` or `task.audit`.
- Execution history: review segment number and config revision count.
- Config revision dialog: inspect current hash and changed fields.
