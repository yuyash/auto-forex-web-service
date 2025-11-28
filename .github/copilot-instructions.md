# Auto Forex Copilot Guide

## Python

- `cd backend && source ./.venv/bin/activate` to activate the virtual environment.
- Use `uv` command to install dependencies.

## Architecture & Domains

- `backend/accounts/` owns auth, OANDA account management, system settings, and email/JWT/rate-limiting helpers consumed by REST views in `accounts/views.py`.
- `backend/trading/` contains every trading concern: strategy definitions (`*_strategy.py`), task-oriented APIs (`strategy_config_views.py`, `backtest_task_views.py`, `trading_task_views.py`), Celery orchestration (`tasks.py`, `athena_import_task.py`), and WebSocket consumers.
- `backend/trading_system/` supplies project wiring plus `config_loader.py`, which merges `config/system.yaml` defaults with env vars; prefer `get_config()` instead of re-reading YAML.
- `frontend/src/` mirrors the task-based backend: `services/api/*.ts` wraps REST endpoints, `hooks/` exposes Fetch/mutation hooks, and `components/tasks/` renders shared forms/metrics for both backtest and live trading flows.

## Configuration Conventions

- Local secrets live in `.env`; for documentation reference `docs/ENVIRONMENT_VARIABLES.md`. Database-backed `SystemSettings` (see `accounts/models.py` + `settings_helper.py`) override envs and are cached for 5 minutes, so call `refresh_settings_cache()` after admin edits.
- Market/strategy behavior is tuned via YAML keys (tick buffering, ATR, scaling, etc.); reuse `trading_system.config_loader.get_config("section.key")` rather than hard-coding defaults.
- Auth tokens are JWTs issued in `accounts/jwt_utils.py`, stored client-side, and attached via `frontend/src/services/api/client.ts`; keep responses consistent with `ApiClient.handleResponse` expectations (JSON, meaningful `message/detail`).

## Backend Workflow

- Use `uv` for everything: `uv run python manage.py runserver`, `uv run celery -A trading_system worker -l info`, and `uv run celery -A trading_system beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler` (see `DEVELOPMENT.md`).
- Celery tasks live in `accounts/tasks.py` (account sync) and `trading/tasks.py` (streaming + execution). Maintain idempotency and respect existing retry/backoff options when adding tasks.
- Strategy engines rely on registries in `trading/register_strategies.py` and base behaviors in `trading/base_strategy.py`; tests expect new strategies to register there and expose risk hooks (ATR, margin guards).
- REST APIs are DRF views split by domain (orders, market configs, events, tasks). Follow serializer patterns in `trading/*_serializers.py` and permissions in `accounts/permissions.py`.

## Frontend Workflow

- Vite dev server runs via `npm run dev`; production build + type-check is `npm run build`. Unit tests use Vitest (`npm run test`, `npm run test:watch`), Playwright E2E via `npm run test:e2e`, and lint/format via `npm run lint` / `npm run format`.
- Task UI is schema-driven: Zod schemas inside `components/tasks/forms` define validation shared across forms; mutation hooks (`useBacktestTaskMutations`, etc.) expect optimistic updates and expose `onSuccess/onError` handlers.
- API layer enforces Bearer auth and rate-limit messaging; when adding endpoints ensure responses align with the typed contracts under `frontend/src/types/` so hooks remain type-safe.

## Testing & Quality Gates

- Backend uses pytest with extensive suites in `backend/tests/` (strategy-specific tests, task APIs, security). Prefer `uv run pytest -m <marker>` to target categories; coverage artifacts land in `backend/htmlcov/`.
- Static checks: `uv run black --check .`, `uv run flake8 .`, `uv run mypy .` with a 100-char limit and full type hints/docstrings on public functions.
- Frontend sticks to ESLint + Prettier via `npm run lint`/`npm run format:check`; keep hooks/components covered by Vitest and interaction flows by Playwright before merging.

## Deployment & Ops

- Docker-first workflows live in `docker-compose.yaml`; `docker-compose up -d`, `docker-compose exec backend python manage.py migrate`, etc., remain the canonical container commands.
- Production automation happens through GitHub Actions (see `docs/github/README.md`) building three images (backend/frontend/nginx) and calling SSH deploys. Local ops scripts under `scripts/*.sh` encapsulate deploy/backup/restore/service management; honor `COMPOSE_FILE` overrides when updating them.
- Logs default to `backend/logs/` and Celery/stream tasks emit detailed context—reuse existing `logger` instances, security logging via `trading/event_logger.py`, and rate-limit audit trails in `accounts/rate_limiter.py` to keep observability consistent.

## Integration Tips

- Market data streaming (`trading/tasks.py`) enforces one stream per active account using Redis cache keys; when touching streaming logic, update both cache invalidation and `TickDataBuffer` flushing to avoid duplicate inserts.
- Frontend real-time UX currently relies on polling hooks (see `useBacktestTaskPolling`); if you add Channels/WebSocket support, route through `trading/consumers.py` to maintain a single event schema.
- Keep cross-component contracts documented: task APIs serve under `/api/backtest-tasks/` and `/api/trading-tasks/`, matching the client helpers in `frontend/src/services/api/`. Update both sides plus the README snippets in `frontend/src/services/api/README.md` when changing signatures.
