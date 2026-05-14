# Backend Hardening Rollout Checklist

Use this checklist for the backend hardening/refactor PR that sanitizes task
errors, adds access-token revocation, batches live tick progress writes, and
introduces bounded OANDA list fan-out.

## PR Notes

- Public task failure payloads now expose fixed `error_message` values and
  stable `error_code` values. Raw exception text, tracebacks, and upstream
  OANDA response bodies remain server-side only.
- Access JWTs include `jti`, `auth_version`, and, when available, a tracked
  `sid`. Logout and password reset can invalidate already-issued access tokens.
- Live tick ingestion and progress persistence are batched using configurable
  latency/count thresholds.
- OANDA order and position list endpoints fetch account data with bounded
  parallelism and bounded upstream history counts.

## Staging Deployment

1. Deploy the branch to staging.
2. Run migrations:
   - `accounts.0006_user_auth_token_version`
   - `trading.0059_alter_backtesttask_description_and_more`
3. Confirm `docs/openapi.json` is published or served by the staging API docs.

## Smoke Tests

Auth:

- Login creates access and refresh cookies.
- Refresh rotates the refresh token and issues a session-bound access token.
- Logout terminates the current session and rejects the previous access token.
- Password reset invalidates previous access tokens.
- Locked users cannot authenticate with previous access tokens.

Tasks:

- Start, stop, fail intentionally, resume, and rerun one backtest.
- Start and stop one dry-run trading task.
- Confirm task detail, execution history, summary, and SSE stream views show the
  fixed failure message plus `TASK_EXECUTION_FAILED`.
- Confirm no API response includes `error_traceback`, raw exception strings, or
  raw OANDA upstream `details`.

Market:

- List orders and positions for one account and for all accounts.
- Confirm partial OANDA account failures return warnings and complete failures
  return `OANDA_UPSTREAM_ERROR`.

## Runtime Knobs

Start with defaults, then tune only after staging observation:

- `LIVE_TICK_BATCH_SIZE`
- `LIVE_TICK_BATCH_MAX_LATENCY_SECONDS`
- `TRADING_LIVE_PROGRESS_FLUSH_BATCHES`
- `TRADING_LIVE_PROGRESS_FLUSH_SECONDS`
- `TRADING_BACKTEST_PROGRESS_FLUSH_BATCHES`
- `TRADING_BACKTEST_PROGRESS_FLUSH_SECONDS`
- `OANDA_LIST_DEFAULT_HISTORY_COUNT`
- `OANDA_LIST_MAX_HISTORY_COUNT`
- `OANDA_LIST_MAX_WORKERS`

## Metrics To Watch

- Database write rate and latency for `execution_state`, positions, and runtime
  metrics tables.
- API p95 latency for task summaries, execution history, market orders, and
  market positions.
- OANDA 429/4xx/5xx counts after bounded list fan-out is enabled.
- Celery trading/backtest queue runtime and heartbeat freshness.

## Follow-Up Work

- Split `TaskExecutor` further behind narrower lifecycle, state, metrics, event,
  and market-guard ports.
- Move the large task/market views toward query serializers plus presenter
  services so API classes stay thin.
