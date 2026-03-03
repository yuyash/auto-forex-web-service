# AGENTS.md - Auto Forex Trader Project Guide

This document provides guidance for AI agents working on this project.

## Backend Architecture

### Django Apps

#### 1. **accounts** - Authentication & User Management

- User model with custom authentication
- JWT token generation and validation
- Session management with Redis backend
- Security monitoring and IP blocking
- User settings and preferences
- Notification preferences
- HTTP access logging middleware

#### 2. **health** - System Health Checks

- Database connectivity checks
- Redis connectivity checks
- Celery worker status
- System resource monitoring (CPU, memory)
- Health check endpoint for load balancers

#### 3. **market** - Market Data & OANDA Integration

- OANDA API integration (v20)
- Real-time market data streaming via WebSocket
- Tick data publishing to Redis pub/sub
- Market data storage and retrieval
- Instrument configuration
- Backtesting data management

#### 4. **trading** - Trading Strategies & Execution

- Trading strategy definitions and configurations
- Strategy execution engine
- Position management and lifecycle
- Order execution and tracking
- Trade history and reconciliation
- Risk management enforcement
- Performance metrics calculation

### Configuration

**Django Settings** (`backend/config/settings.py`):

- Database: PostgreSQL with connection pooling
- Cache: Redis with Django cache framework
- Session: Redis-backed sessions
- Celery: Redis broker with task routing
- Channels: Redis channel layer for WebSocket
- Logging: Rotating file handlers with per-app loggers
- Security: HTTPS, HSTS, CSRF, XFrame protection, Content Security Policy (CSP)
- CORS: Configurable allowed origins
- JWT: HS256 algorithm with dedicated JWT_SECRET_KEY, 1-hour access token expiration
- Refresh Tokens: Opaque DB-backed tokens, 7-day expiration, rotation on use, family revocation on reuse detection

**Environment Variables** (`.env`):

- `DB_PASSWORD` - PostgreSQL password
- `SECRET_KEY` - Django secret key (min 50 chars)
- `JWT_SECRET_KEY` - JWT signing key (must differ from SECRET_KEY)
- `REDIS_PASSWORD` - Redis password (optional)
- `REFRESH_TOKEN_EXPIRATION` - Refresh token lifetime in seconds (default: 604800 / 7 days)
- Additional config via environment variables

### API Structure

**Base URL**: `/api/`

**Authentication**: JWT Bearer token in `Authorization` header. Refresh via `POST /api/auth/refresh` with `refresh_token` in request body (no Bearer header needed).

**Response Format**: JSON with consistent error structure

**Endpoints**:

- `/api/auth/` - Authentication (login, logout, token refresh via refresh_token)
- `/api/accounts/` - User account management
- `/api/oanda/` - OANDA account integration
- `/api/market/` - Market data queries
- `/api/strategies/` - Strategy management
- `/api/positions/` - Position queries
- `/api/trades/` - Trade history
- `/api/health/` - System health checks
- `/api/docs/` - Swagger UI (development only)
- `/api/redoc/` - ReDoc (development only)

### Celery Task Architecture

**Task Queues**:

- `default` - General tasks
- `market` - Long-running market data tasks
- `trading` - Strategy execution and backtesting tasks

**Celery Beat Scheduler**: Uses database scheduler for persistent scheduled tasks

---

## Frontend Architecture

### Routing (`App.tsx`)

All page components are lazy-loaded via `React.lazy()`. Uses `react-router-dom`.

**Public routes**: `/login`, `/register` (conditionally enabled via `systemSettings`)

**Protected routes** (wrapped in `ProtectedRoute` + `AppLayout`):

| Path                       | Page                      |
| -------------------------- | ------------------------- |
| `/dashboard`               | `DashboardPage`           |
| `/configurations`          | `ConfigurationsPage`      |
| `/configurations/:id`      | `ConfigurationDetailPage` |
| `/configurations/new`      | `ConfigurationFormPage`   |
| `/configurations/:id/edit` | `ConfigurationFormPage`   |
| `/backtest-tasks`          | `BacktestTasksPage`       |
| `/backtest-tasks/new`      | `BacktestTaskFormPage`    |
| `/backtest-tasks/:id`      | `BacktestTaskDetailPage`  |
| `/backtest-tasks/:id/edit` | `BacktestTaskFormPage`    |
| `/trading-tasks`           | `TradingTasksPage`        |
| `/trading-tasks/new`       | `TradingTaskFormPage`     |
| `/trading-tasks/:id`       | `TradingTaskDetailPage`   |
| `/trading-tasks/:id/edit`  | `TradingTaskFormPage`     |
| `/settings`                | `SettingsPage`            |
| `/settings/accounts/:id`   | `OandaAccountDetailPage`  |
| `/profile`                 | `ProfilePage`             |

**Provider hierarchy**: `ErrorBoundary` → `AccessibilityProvider` → `ThemeProvider` → `QueryProvider` → `ToastProvider` → `BrowserRouter` → `AuthProvider`

### Component Organization (`src/components/`)

- `auth/` - `ProtectedRoute`
- `backtest/` - `BacktestTaskCard`, `BacktestTaskForm`, `BacktestTaskDetail`, `FloorLayerLog`, `detail/`
- `charts/` - `EquityOHLCChart` (react-financial-charts + d3)
- `common/` - Shared UI: `DataTable`, `VirtualizedTable`, `VirtualizedList`, `ConfirmDialog`, `Toast`, `ErrorBoundary`, `PageErrorBoundary`, `ValidatedTextField`, `FormFieldError`, `FormErrorSummary`, `LoadingSpinner`, `SkeletonLoader`, `Breadcrumbs`, `SkipLinks`, `GlobalKeyboardShortcuts`, `ChartContainer`, `TaskControlButtons`, `ExecutionDataProvider`, `LazyTabPanel`, `LanguageSelector`
- `configurations/` - `ConfigurationCard`, `ConfigurationForm`, `ParametersForm`, `ConfigurationDeleteDialog`, `strategyConfigSchemas.ts`
- `dashboard/` - `ActiveTasksWidget`, `MarketChart`, `OpenOrdersPanel`, `OpenPositionsPanel`, `QuickActionsWidget`, `RecentBacktestsWidget`
- `layout/` - `AppLayout`, `AppHeader`, `AppFooter`, `Sidebar`, `ResponsiveNavigation`
- `settings/` - `AccountManagement`, `AddAccountModal`, `PreferencesForm`, `StrategyDefaults`
- `strategy/` - `StrategyConfigForm`, `StrategyControls`, `StrategySelector`, `StrategyStatus`
- `tasks/` - Shared task components: `actions/`, `charts/`, `detail/`, `display/`, `forms/`, `TaskProgress`
- `trading/` - `TradingTaskCard`, `TradingTaskForm`, `TradingTaskDetail`, `TradingTaskChart`, `detail/`

### API Layer

**Two-layer architecture**:

1. `src/api/` - Low-level Axios client with JWT interceptor (auto-refresh on 401)
2. `src/services/api/` - Domain-specific API services:
   - `accounts.ts`, `backtestTasks.ts`, `tradingTasks.ts`, `configurations.ts`, `strategies.ts`, `market.ts`

**Polling services** (`src/services/polling/`):

- `TaskPollingService` - HTTP polling with exponential backoff (interval: 3s, maxRetries: 5)
- `TickPollingService` - Market tick polling

## Development Workflow

### Local Development Setup

**Option 1: Local Development (Without Docker)**

Prerequisites:

- Python 3.13+
- Node.js 18+
- PostgreSQL 17
- Redis 7
- uv (Python package manager)

Setup:

```bash
# Backend
cd backend
cp .env.example .env
uv sync --all-extras
uv run python manage.py migrate
uv run python manage.py createsuperuser

# Frontend
cd frontend
npm install
```

Run (4 terminal windows):

```bash
# Terminal 1: Django
cd backend && uv run python manage.py runserver 0.0.0.0:8000

# Terminal 2: Celery Worker
cd backend && uv run celery -A config worker -l info --concurrency=4

# Terminal 3: Celery Beat
cd backend && uv run celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Terminal 4: React
cd frontend && npm run dev
```

**Option 2: Docker Development**

```bash
cp .env.example .env
docker-compose build
docker-compose up -d
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser
```

Access:

- Frontend: http://localhost:5173 (dev) or http://localhost (Docker)
- Backend API: http://localhost:8000/api
- Admin: http://localhost:8000/admin
- API Docs: http://localhost:8000/api/docs

### Code Quality Tools

**Backend**:

- **Linting**: `ruff check .` - Fast Python linter
- **Formatting**: `ruff format .` - Code formatter
- **Type Checking**: `ty check` - Type checker
- **Security**: `bandit` - Security issue detection
- **Docstring Coverage**: `interrogate` - Docstring coverage

**Frontend**:

- **Linting**: `npm run lint` - ESLint
- **Formatting**: `npm run format` - Prettier
- **Type Checking**: `npm run build` - TypeScript compilation

**Pre-commit Hooks** (`.pre-commit-config.yaml`):

- Trailing whitespace, file endings
- YAML, JSON, TOML validation
- Ruff lint and format
- Type checking (ty)
- Security checks (bandit)
- Docstring coverage (interrogate)
- Prettier formatting
- Django system checks
- ESLint and TypeScript checks
- Pytest and Vitest (on pre-push)

### Testing

**Backend Tests**:

```bash
# Unit tests
uv run pytest tests/unit/ -v

# Integration tests
uv run pytest tests/integration/ -v

# All tests with coverage
uv run pytest --cov=. --cov-report=html

# Specific test file
uv run pytest tests/unit/test_auth.py -v

# Tests matching pattern
uv run pytest -k "test_login" -v
```

**Frontend Tests**:

```bash
# Unit tests
npm run test

# Watch mode
npm run test:watch

# UI mode
npm run test:ui

# E2E tests
npm run test:e2e
```

**Test Configuration**:

- Backend: pytest with pytest-django, pytest-cov, pytest-xdist
- Frontend: Vitest with React Testing Library
- E2E: Playwright
- Coverage threshold: 60% (backend)

### Database Migrations

```bash
# Create migrations
uv run python manage.py makemigrations

# Apply migrations
uv run python manage.py migrate

# Show migration status
uv run python manage.py showmigrations

# Reverse migration
uv run python manage.py migrate app_name 0001
```

### Django Management Commands

```bash
# Create superuser
uv run python manage.py createsuperuser

# Create regular user
uv run python manage.py create_user --username user1 --email user1@example.com

# Delete user
uv run python manage.py delete_user --username user1

# Django shell
uv run python manage.py shell

# Collect static files
uv run python manage.py collectstatic --noinput

# System checks
uv run python manage.py check
```

## CI/CD Pipeline

### GitHub Actions Workflows

**1. Test Workflow** (`.github/workflows/test.yml`)

- Triggers: Pull requests to main/develop
- Backend tests:
  - Ruff lint and format check
  - Type checking (ty)
  - Unit tests with coverage
  - Integration tests with parallel execution
  - Coverage threshold check (60%)
- Frontend tests:
  - ESLint
  - TypeScript type check
  - Vitest
- Docker Compose validation

**2. Build and Deploy Workflow** (`.github/workflows/build-and-deploy.yml`)

- Triggers: Push to main/develop, pull requests
- Build backend Docker image (multi-platform: amd64, arm64)
- Build frontend Docker image (multi-platform: amd64, arm64)
- Push to DockerHub
- Deploy to production (main branch only)
- Verify deployment health

**3. API Documentation Workflow** (`.github/workflows/api-docs.yml`)

- Generates OpenAPI schema
- Publishes API documentation

### Deployment Process

**Production Deployment**:

1. Push to main branch triggers build workflow
2. Docker images built and pushed to DockerHub
3. SSH into production server
4. Pull latest images
5. Run migrations
6. Restart services
7. Verify health checks

**Environment Variables** (Production):

- `DEBUG=False`
- `ALLOWED_HOSTS` - Production domain
- `SECRET_KEY` - Secure random key
- `DB_PASSWORD` - Secure database password
- `REDIS_PASSWORD` - Secure Redis password
- `OANDA_PRACTICE_API` - OANDA practice endpoint
- `OANDA_LIVE_API` - OANDA live endpoint
- AWS credentials for backtesting
