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

### 3. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Copy environment file
cp .env.example .env

# Edit .env with your local settings
# Make sure these are set:
# DB_HOST=localhost
# DB_PORT=5432
# REDIS_URL=redis://localhost:6379/0
# DEBUG=True

# Install Python dependencies
uv sync --all-extras

# Run migrations
uv run python manage.py migrate

# Create superuser
uv run python manage.py createsuperuser

# Collect static files
uv run python manage.py collectstatic --noinput
```

### 4. Frontend Setup

```bash
# Navigate to frontend directory (from project root)
cd frontend

# Install dependencies
npm install
```

### 5. Generate Security Keys

```bash
# Generate Django SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Update this value in `backend/.env`.

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

### 1. Setup Environment Variables

```bash
# Copy environment file
cp .env.example .env

# Edit .env with your settings
# Minimum required:
# - DB_PASSWORD
# - SECRET_KEY
```

### 2. Generate Security Keys

```bash
# Generate Django SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Update this value in `.env`.

### 3. Build and Start Services

```bash
# Build all containers
docker-compose build

# Start all services in detached mode
docker-compose up -d

# View logs (optional)
docker-compose logs -f
```

### 4. Initialize Database

```bash
# Run migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec backend python manage.py createsuperuser

# Collect static files (if needed)
docker-compose exec backend python manage.py collectstatic --noinput
```

### 5. Access the Application

- **Frontend**: http://localhost (via Nginx on port 80)
- **Backend API**: http://localhost/api
- **Admin Panel**: http://localhost/admin
- **Direct Backend**: http://localhost:8000 (bypassing Nginx)
- **Direct Frontend**: http://localhost:5173 (bypassing Nginx)

### 6. Useful Docker Commands

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes database data)
docker-compose down -v

# Restart a specific service
docker-compose restart backend

# View logs for specific service
docker-compose logs -f backend

# Execute command in container
docker-compose exec backend python manage.py shell

# Rebuild specific service
docker-compose build backend

# View running containers
docker-compose ps
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
docker-compose exec backend pytest
```

#### Code Quality Checks

```bash
# Format code
cd backend
uv run black .

# Lint code
uv run flake8 .

# Type checking
uv run mypy .

# Run all checks
uv run black --check . && uv run flake8 . && uv run mypy .
```

#### Database Operations

```bash
# Create migrations (local)
cd backend
uv run python manage.py makemigrations

# Create migrations (Docker)
docker-compose exec backend python manage.py makemigrations

# Apply migrations (local)
uv run python manage.py migrate

# Apply migrations (Docker)
docker-compose exec backend python manage.py migrate

# Django shell (local)
uv run python manage.py shell

# Django shell (Docker)
docker-compose exec backend python manage.py shell
```

### Frontend Development

#### Running Tests

```bash
# Local development
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

# Check formatting
npm run format:check

# Type checking
npm run build  # TypeScript compilation happens during build
```

#### Build for Production

```bash
cd frontend
npm run build
```

### Monitoring Logs

#### Local Development

```bash
# Backend logs are in terminal where runserver is running
# Celery logs are in terminal where worker is running
# Frontend logs are in terminal where npm run dev is running

# Application logs
tail -f backend/logs/django.log
tail -f backend/logs/celery.log
```

#### Docker Development

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f celery
docker-compose logs -f frontend

# Last 100 lines
docker-compose logs --tail=100 backend
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
docker-compose ps postgres
docker-compose logs postgres
```

#### Redis Connection Error

```bash
# Check Redis is running
# Local:
brew services list | grep redis  # macOS
sudo systemctl status redis      # Linux
redis-cli ping  # Should return PONG

# Docker:
docker-compose ps redis
docker-compose logs redis
```

#### Migration Errors

```bash
# Reset database (WARNING: deletes all data)
# Local:
cd backend
uv run python manage.py flush

# Docker:
docker-compose exec backend python manage.py flush

# Or drop and recreate database
# Local:
sudo -u postgres psql
DROP DATABASE forex_trading;
CREATE DATABASE forex_trading;
GRANT ALL PRIVILEGES ON DATABASE forex_trading TO postgres;
\q

# Then run migrations again
```

#### Celery Not Processing Tasks

```bash
# Check Celery worker is running
# Check Redis connection
# Check Celery logs for errors

# Restart Celery (local)
# Stop with Ctrl+C and restart

# Restart Celery (Docker)
docker-compose restart celery
docker-compose restart celery-beat
```

### Frontend Issues

#### Port Already in Use

```bash
# Find process using port 5173
lsof -i :5173

# Kill the process
kill -9 <PID>

# Or use different port
cd frontend
npm run dev -- --port 3000
```

#### Module Not Found Errors

```bash
# Reinstall dependencies
cd frontend
rm -rf node_modules package-lock.json
npm install
```

#### Build Errors

```bash
# Clear cache and rebuild
cd frontend
rm -rf node_modules dist .vite
npm install
npm run build
```

### Docker Issues

#### Container Won't Start

```bash
# Check logs
docker-compose logs <service-name>

# Rebuild container
docker-compose build <service-name>
docker-compose up -d <service-name>
```

#### Port Conflicts

```bash
# Check what's using the port
lsof -i :8000  # Backend
lsof -i :5173  # Frontend
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis

# Stop conflicting service or change port in docker-compose.yaml
```

#### Volume Permission Issues

```bash
# Fix permissions
sudo chown -R $USER:$USER .

# Or remove volumes and recreate
docker-compose down -v
docker-compose up -d
```

#### Out of Disk Space

```bash
# Clean up Docker
docker system prune -a --volumes

# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune
```

### General Issues

#### Environment Variables Not Loading

```bash
# Make sure .env file exists
ls -la .env

# Check file format (no spaces around =)
cat .env

# Restart services after changing .env
# Local: Restart all terminal processes
# Docker: docker-compose down && docker-compose up -d
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
2. Check [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md) for configuration details
3. Review the API documentation at http://localhost:8000/api/docs
4. Explore the admin panel at http://localhost:8000/admin
5. Start developing your features!

## Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)
- [Material-UI Documentation](https://mui.com/)
- [Celery Documentation](https://docs.celeryproject.org/)
