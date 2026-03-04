# AGENTS.md - Auto Forex Trader Project Guide

This document provides guidance for AI agents working on this project.
Backend- and frontend-specific details live in `backend/AGENTS.md` and `frontend/AGENTS.md` respectively.
This file covers project-wide architecture, infrastructure, CI/CD, and development workflow rules.

## Overview

Auto Forex Trader is a full-stack web application for managing algorithmic forex trading on OANDA accounts.
It provides real-time market data streaming, modular strategy execution, position tracking, backtesting, and risk management.

### Repository Layout

```
.
├── backend/              # Django 5.2 LTS application (REST API, WebSocket, Celery workers)
├── frontend/             # React 19 + TypeScript + Vite SPA
├── nginx/                # Reverse proxy configs (dev & prod Dockerfiles, conf.d/)
├── docs/                 # Generated OpenAPI schema (openapi.json), GitHub Pages API docs
├── docker-compose.yaml   # Development stack (builds from source)
├── docker-compose.prod.yaml  # Production stack (pulls pre-built images from DockerHub)
├── .github/              # GitHub Actions workflows & Dependabot
├── .pre-commit-config.yaml
├── .env.example          # Secrets-only template (DB_PASSWORD, SECRET_KEY, JWT_SECRET_KEY, REDIS_PASSWORD)
└── DEVELOPMENT.md        # Detailed local & Docker dev setup guide
```

## Architecture

The system runs as a set of Docker containers on a single host:

| Service     | Role                                                  |
| ----------- | ----------------------------------------------------- |
| nginx       | Reverse proxy, SSL termination (prod), static files   |
| backend     | Django + Daphne (ASGI) — REST API & WebSocket server  |
| celery      | Async task workers (queues: default, trading, market) |
| celery-beat | Periodic task scheduler (django-celery-beat)          |
| frontend    | React SPA served by its own Nginx container           |
| postgres    | PostgreSQL 17                                         |
| redis       | Cache, session store, Celery broker                   |
| certbot     | Let's Encrypt certificate renewal (prod only)         |

All services communicate over a Docker bridge network (`forex_network`).
In development, `docker-compose.yaml` builds images from source and mounts local code for hot-reload.
In production, `docker-compose.prod.yaml` pulls pre-built images from DockerHub and adds SSL via certbot.

## Technology Stack

| Layer          | Technologies                                                      |
| -------------- | ----------------------------------------------------------------- |
| Backend        | Python 3.13, Django 5.2 LTS, DRF, Django Channels, Celery, Daphne |
| Frontend       | React 19, TypeScript, Vite, Material-UI, react-financial-charts   |
| Database       | PostgreSQL 17                                                     |
| Cache/Broker   | Redis 7                                                           |
| Infrastructure | Docker, Docker Compose, Nginx, Let's Encrypt                      |
| CI/CD          | GitHub Actions, DockerHub (multi-arch amd64/arm64)                |
| Package Mgmt   | uv (Python), npm (Node.js)                                        |
| Linting        | ruff, ty (backend), ESLint, Prettier (frontend)                   |
| Testing        | pytest + hypothesis (backend), Vitest + Playwright (frontend)     |
| Security       | bandit (SAST), detect-private-key, Dependabot                     |
| API Docs       | drf-spectacular → OpenAPI JSON → Swagger UI on GitHub Pages       |

## Security Considerations

- Never commit `.env` files. Only `.env.example` (with placeholder values) is tracked.
- `SECRET_KEY` and `JWT_SECRET_KEY` must be distinct, cryptographically random, and at least 50 characters.
- OANDA API tokens are encrypted at rest with Fernet.
- The backend enforces JWT authentication with refresh-token rotation and family revocation.
- CSP, HSTS, X-Frame-Options DENY, and CSRF protection are enabled in production.
- `bandit` runs as a pre-commit hook for Python SAST.
- `detect-private-key` pre-commit hook prevents accidental key commits.
- AWS credentials are mounted read-only (`~/.aws:/root/.aws:ro`) — never bake them into images.
- Rate limiting and IP-based blocking protect authentication endpoints.

## Build & Test

### Docker (recommended)

```bash
# Build and start all services
docker compose build
docker compose up -d

# Run backend tests
docker compose exec backend pytest

# Run frontend tests
docker compose exec frontend npm run test
```

### Local Development

See `DEVELOPMENT.md` for full instructions. Summary:

```bash
# Backend
cd backend
uv sync --all-extras
uv run pytest                          # tests
uv run ruff check . && uv run ruff format --check .  # lint
uv run ty check                        # type check

# Frontend
cd frontend
npm ci
npm run test                           # Vitest
npm run lint                           # ESLint
npx tsc --noEmit                       # type check
```

### Pre-commit Hooks

Pre-commit is configured at the repo root.
Several hooks (ty, Django checks, pytest) invoke tools from the backend Python virtualenv,
so you must activate it before running pre-commit or committing:

```bash
source backend/.venv/bin/activate
pre-commit install --install-hooks -t pre-commit -t pre-push
```

The virtualenv must also be active for `git commit` and `git push` to succeed, since the hooks shell out to `backend/.venv/bin/`.

On every commit (pre-commit stage):

- Trailing whitespace, EOF fixer, YAML/JSON/TOML checks, large file guard, merge conflict detection, private key detection
- `ruff check --fix` and `ruff format` on `backend/`
- `ty check` on `backend/`
- `bandit` security scan on `backend/`
- `interrogate` docstring coverage on `backend/`
- `prettier` formatting on `frontend/` (ts, tsx, js, jsx, json, css, md)
- `eslint` on `frontend/`
- TypeScript type check (`tsc --noEmit`) on `frontend/`
- Django system check, migration check, and OpenAPI schema generation

On every push (pre-push stage):

- `pytest` on `backend/`
- Frontend build check (`npm run build`)
- `npm ci` lockfile integrity check
- `vitest` on `frontend/`

### CI (GitHub Actions)

| Workflow               | Trigger                         | What it does                                                                                               |
| ---------------------- | ------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `test.yml`             | PR → main, develop              | Lint + type-check + unit/integration tests (backend & frontend), coverage ≥ 60%, Docker Compose validation |
| `build-and-deploy.yml` | Push/PR → main, develop         | Build multi-arch Docker images, push to DockerHub, deploy to production on `main` push                     |
| `version-bump.yml`     | Push → main                     | Auto-bump version (major/minor/patch) from conventional commits, create PR                                 |
| `api-docs.yml`         | Push → main (API-related paths) | Generate OpenAPI schema, deploy Swagger UI to GitHub Pages                                                 |

## Commit and Push

### Branching Strategy

1. Always create a new branch from `main`:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b <type>/<short-description>
   ```
2. Branch naming convention: `<type>/<short-description>` (e.g., `feat/add-trailing-stop`, `fix/margin-calc-error`, `chore/update-deps`).
3. Push the branch and open a Pull Request targeting `main` (or `develop` for staging).

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <description>

[optional body]

[optional footer(s)]
```

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.

Examples:

- `feat(strategy): add trailing stop-loss to floor strategy`
- `fix(auth): prevent refresh token reuse after revocation`
- `docs: update API endpoint descriptions`
- `chore(deps): bump Django to 5.2.1`

Breaking changes: append `!` after type/scope (e.g., `feat(api)!: remove v1 endpoints`) or add `BREAKING CHANGE:` in the footer.

The `version-bump.yml` workflow reads these prefixes to determine semver bumps:

- `feat` → minor
- `fix`, `perf`, `refactor` → patch
- `!` or `BREAKING CHANGE` → major

### Pre-commit / Pre-push Checks

All hooks described in the "Build & Test" section run automatically.
Do not use `--no-verify` to skip them — CI will catch the same issues and block the PR.

### Pull Request Rules

- PRs require passing CI checks before merge.
- Keep PRs focused — one feature or fix per PR.
- Update or add tests for any behavioral change.
- Update `docs/openapi.json` if API endpoints change (auto-generated by pre-commit hook).

## Deploy

### Production Deployment (Automated)

Merging to `main` triggers the `build-and-deploy.yml` workflow:

1. Builds multi-arch (amd64/arm64) Docker images for backend and frontend.
2. Pushes images to DockerHub with tags: `latest`, branch name, and commit SHA.
3. SSHs into the production server and:
   - Copies `docker-compose.prod.yaml` and `nginx/` config.
   - Pulls latest images.
   - Runs `docker compose down && docker compose up -d`.
   - Syncs PostgreSQL password if needed.
   - Prunes old images.
   - Verifies all services are healthy.

### Required GitHub Secrets

| Secret               | Description                          |
| -------------------- | ------------------------------------ |
| `DOCKERHUB_USERNAME` | DockerHub account username           |
| `DOCKERHUB_TOKEN`    | DockerHub access token               |
| `SSH_PRIVATE_KEY`    | SSH key for production server access |
| `SERVER_HOST`        | Production server hostname/IP        |
| `SERVER_USER`        | SSH user on production server        |
| `DEPLOY_PATH`        | Deployment directory on server       |
| `SSH_PORT`           | SSH port (default: 22)               |

### Manual Deployment

```bash
# On the production server
cd /path/to/deploy
docker compose pull
docker compose down
docker compose up -d
```

### SSL Certificates

Production uses Let's Encrypt via certbot (auto-renewal every 12 hours).
Initial certificate generation:

```bash
docker compose run --rm certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  -d yourdomain.com -d www.yourdomain.com
```
