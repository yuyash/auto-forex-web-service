# Development Guide

This guide covers local development setup for the Auto Forex Trader without SSL/HTTPS.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Option 1: Local Development (Without Docker)](#option-1-local-development-without-docker)
- [Option 2: Docker Development (Without SSL)](#option-2-docker-development-without-ssl)
- [Common Development Tasks](#common-development-tasks)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### For Local Development (Option 1)

- Python 3.13+
- Node.js 18+ and npm
- PostgreSQL 17
- Redis 7
- uv (Python package manager)

### For Docker Development (Option 2)

- Docker 20.10+
- Docker Compose 2.0+

---

## Project Structure

```
.
├── backend/             # Django application
│   ├── apps/            # Django apps
│   ├── config/          # Django settings
│   ├── requirements.txt # Python dependencies
│   └── Dockerfile       # Backend container
├── frontend/            # React application
│   ├── src/             # React components
│   ├── package.json     # Node dependencies
│   └── Dockerfile       # Frontend container
├── nginx/               # Nginx configuration
│   ├── nginx.conf       # Nginx config
│   └── Dockerfile       # Nginx container
├── docker-compose.yaml  # Docker Compose configuration
└── README.md            # This file
```

## Option 1: Local Development (Without Docker)

Run backend and frontend directly on your machine without Docker.

### 1. Install System Dependencies

#### macOS (using Homebrew)

```bash
# Install PostgreSQL
brew install postgresql@17
brew services start postgresql@17

# Install Redis
brew install redis
brew services start redis

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Node.js (if not already installed)
brew install node
```

#### Linux (Ubuntu/Debian)

```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql-17 postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Install Redis
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

### 2. Setup PostgreSQL Database

```bash
# Create database and user
sudo -u postgres psql

# In PostgreSQL shell:
CREATE DATABASE "auto-forex";
CREATE USER postgres WITH PASSWORD 'postgres';
ALTER ROLE postgres SET client_encoding TO 'utf8';
ALTER ROLE postgres SET default_transaction_isolation TO 'read committed';
ALTER ROLE postgres SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE "auto-forex" TO postgres;
\q
```

### 3. Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Generate SECRET_KEY, JWT_SECRET_KEY, and the OANDA token encryption key,
# then paste them into .env
python -c "from django.core.management.utils import get_random_secret_key; print('SECRET_KEY=' + get_random_secret_key())"
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(64))"
python -c "from cryptography.fernet import Fernet; print('OANDA_TOKEN_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"

# Edit .env — set at minimum:
#   DB_PASSWORD=<your postgres password>
#   SECRET_KEY=<generated above>
#   JWT_SECRET_KEY=<generated above, must differ from SECRET_KEY>
#   OANDA_TOKEN_ENCRYPTION_KEY=<generated above>
#   DB_HOST=localhost
#   REDIS_URL=redis://localhost:6379/0
#   DEBUG=True
```

If you rotate `OANDA_TOKEN_ENCRYPTION_KEY`, keep the previous key in
`OANDA_TOKEN_ENCRYPTION_FALLBACK_KEYS` until all saved OANDA account tokens have
been re-encrypted. The production rollout sequence is documented in
[docs/oanda-key-rotation.md](docs/oanda-key-rotation.md).

Existing environments that still have plaintext `refresh_tokens.token` rows must
run `uv run python manage.py migrate` before deploying the new auth code. The
included migration hashes legacy rows in place.

### 4. Backend Setup

```bash
cd backend

uv sync --all-extras
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py collectstatic --noinput
```

### 5. Frontend Setup

```bash
cd ../frontend
npm install
```

### 6. Start Development Servers

You'll need 4 terminal windows/tabs:

#### Terminal 1: Django Backend

```bash
cd backend
uv run python manage.py runserver 0.0.0.0:8000
```

Backend will be available at: http://localhost:8000

#### Terminal 2: Celery Worker

```bash
cd backend
uv run celery -A config worker -l info --concurrency=4
```

#### Terminal 3: Celery Beat (Scheduler)

```bash
cd backend
uv run celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

#### Terminal 4: React Frontend

```bash
cd frontend
npm run dev
```

Frontend will be available at: http://localhost:5173

### 7. Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000/api
- **Admin Panel**: http://localhost:8000/admin
- **API Documentation**: http://localhost:8000/api/docs

---

## Option 2: Docker Development (Without SSL)

Run the entire stack using Docker Compose without SSL/HTTPS configuration.

### 1. Configure Environment Variables

```bash
cd backend

# Copy the example file
cp .env.example .env

# Generate SECRET_KEY, JWT_SECRET_KEY, and the OANDA token encryption key,
# then paste them into .env
python -c "from django.core.management.utils import get_random_secret_key; print('SECRET_KEY=' + get_random_secret_key())"
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(64))"
python -c "from cryptography.fernet import Fernet; print('OANDA_TOKEN_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"

# Edit .env — set at minimum:
#   DB_PASSWORD=<your password>
#   SECRET_KEY=<generated above>
#   JWT_SECRET_KEY=<generated above, must differ from SECRET_KEY>
#   OANDA_TOKEN_ENCRYPTION_KEY=<generated above>
```

### 2. Build and Start Services

```bash
# Return to project root
cd ..

# Build all containers
docker compose build

# Start all services in detached mode
docker compose up -d

# View logs (optional)
docker compose logs -f
```

### 3. Initialize Database

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py collectstatic --noinput
```

### 4. Access the Application

- **Frontend**: http://localhost (via Nginx on port 80)
- **Backend API**: http://localhost/api
- **Admin Panel**: http://localhost/admin
- **Direct Backend**: http://localhost:8000 (bypassing Nginx)
- **Direct Frontend**: http://localhost:5173 (bypassing Nginx)

### 5. Useful Docker Commands

```bash
# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes database data)
docker compose down -v

# Restart a specific service
docker compose restart backend

# View logs for specific service
docker compose logs -f backend

# Execute command in container
docker compose exec backend python manage.py shell

# Rebuild specific service
docker compose build backend

# View running containers
docker compose ps
```

---

## Common Development Tasks

### Backend Development

#### Running Tests

```bash
# Local development
cd backend
uv run pytest

# With coverage
uv run pytest --cov=. --cov-report=html

# Docker
docker compose exec backend pytest
```

#### Code Quality Checks

```bash
cd backend

# Lint code
uv run ruff check .

# Lint and auto-fix
uv run ruff check --fix .

# Format code
uv run ruff format .

# Type checking
uv run ty check

# Run all checks
uv run ruff check . && uv run ruff format --check . && uv run ty check
```

#### Database Operations

```bash
# Create migrations (local)
cd backend
uv run python manage.py makemigrations

# Create migrations (Docker)
docker compose exec backend python manage.py makemigrations

# Apply migrations (local)
uv run python manage.py migrate

# Apply migrations (Docker)
docker compose exec backend python manage.py migrate

# Django shell (local)
uv run python manage.py shell

# Django shell (Docker)
docker compose exec backend python manage.py shell
```

### Frontend Development

#### Running Tests

```bash
cd frontend
npm run test

# Watch mode
npm run test:watch

# With UI
npm run test:ui

# E2E tests
npm run test:e2e
```

#### Code Quality Checks

```bash
cd frontend

# Lint
npm run lint

# Format
npm run format

# Type checking
npm run build
```

#### Build for Production

```bash
cd frontend
npm run build
```

### Monitoring Logs

#### Loading Historical Tick Data

The system can load tick data from AWS Athena or CSV files via the management command.

```bash
# Load from Athena (specific date range)
# Local:
cd backend
uv run python manage.py load_data \
  --start 2026-03-01 --end 2026-03-22 \
  --database your_db --table your_table \
  --instrument C:USD-JPY

# Docker:
docker compose exec backend python manage.py load_data \
  --start 2026-03-01 --end 2026-03-22 \
  --database your_db --table your_table \
  --instrument C:USD-JPY

# Load from CSV
uv run python manage.py load_data --from-csv /path/to/ticks.csv

```

Set `LOAD_DATA_DATABASE` and `LOAD_DATA_TABLE` in your `.env` file if you want the management command to read Athena configuration from the environment. See `.env.example` for all options.

#### Local Development

```bash
# Application logs
tail -f backend/logs/django.log
tail -f backend/logs/celery.log
```

#### Docker Development

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f celery
docker compose logs -f frontend

# Last 100 lines
docker compose logs --tail=100 backend
```

---

## Troubleshooting

### Backend Issues

#### Database Connection Error

```bash
# Check PostgreSQL is running
# Local:
brew services list | grep postgresql  # macOS
sudo systemctl status postgresql      # Linux

# Docker:
docker compose ps postgres
docker compose logs postgres
```

#### Redis Connection Error

```bash
# Check Redis is running
# Local:
brew services list | grep redis  # macOS
sudo systemctl status redis      # Linux
redis-cli ping  # Should return PONG

# Docker:
docker compose ps redis
docker compose logs redis
```

#### Migration Errors

```bash
# Reset database (WARNING: deletes all data)
# Local:
cd backend
uv run python manage.py flush

# Docker:
docker compose exec backend python manage.py flush
```

#### Celery Not Processing Tasks

```bash
# Restart Celery (local): stop with Ctrl+C and restart
# Restart Celery (Docker):
docker compose restart celery
docker compose restart celery-beat
```

### Frontend Issues

#### Port Already in Use

```bash
lsof -i :5173
kill -9 <PID>

# Or use different port
cd frontend
npm run dev -- --port 3000
```

#### Module Not Found Errors

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Docker Issues

#### Container Won't Start

```bash
docker compose logs <service-name>
docker compose build <service-name>
docker compose up -d <service-name>
```

#### Port Conflicts

```bash
lsof -i :8000  # Backend
lsof -i :5173  # Frontend
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis
```

#### Out of Disk Space

```bash
docker system prune -a --volumes
```

### General Issues

#### Environment Variables Not Loading

```bash
# Make sure backend/.env file exists
ls -la backend/.env

# Check file format (no spaces around =)
cat backend/.env

# Restart services after changing backend/.env
# Local: Restart all terminal processes
# Docker: docker compose down && docker compose up -d
```

#### CORS Errors

```bash
# Check ALLOWED_HOSTS in backend/.env
# Should include: localhost,127.0.0.1

# Check Django CORS settings in backend/config/settings.py
# Make sure frontend URL is in CORS_ALLOWED_ORIGINS
```

---

## Next Steps

After setting up your development environment:

1. Read the [README.md](README.md) for project overview
2. Review the API documentation at http://localhost:8000/api/docs
3. Explore the admin panel at http://localhost:8000/admin
