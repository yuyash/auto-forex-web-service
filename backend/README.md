# Auto Forex Trading System - Backend

Django 5.2 backend for the Auto Forex Trading System.

## Technology Stack

- **Framework**: Django 5.2 LTS
- **API**: Django REST Framework
- **WebSocket**: Django Channels with Redis
- **Task Queue**: Celery with Redis broker
- **Database**: PostgreSQL 17
- **Cache**: Redis 7
- **Package Manager**: uv
- **Python Version**: 3.13+

## Dependencies

### Core Dependencies

- Django 5.2
- Django REST Framework
- Django Channels
- Celery
- v20 (OANDA API)
- boto3 (AWS S3/Athena)
- psycopg (PostgreSQL driver)
- redis
- django-redis

### Development Dependencies

- pytest
- pytest-django
- pytest-cov
- pytest-asyncio
- black (code formatting)
- flake8 (linting)
- mypy (type checking)
- django-stubs
- djangorestframework-stubs

## Setup

### Prerequisites

- Python 3.13+
- uv package manager
- PostgreSQL 17
- Redis 7

### Installation

1. Install dependencies:

```bash
uv sync --all-extras
```

2. Copy environment variables:

```bash
cp .env.example .env
```

3. Update `.env` with your configuration

4. Run migrations:

```bash
uv run python manage.py migrate
```

5. Create superuser:

```bash
uv run python manage.py createsuperuser
```

## Development

### Running the Development Server

```bash
uv run python manage.py runserver
```

### Running Celery Worker

```bash
uv run celery -A trading_system worker -l info
```

### Running Celery Beat (Scheduler)

```bash
uv run celery -A trading_system beat -l info
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=. --cov-report=html

# Run specific test file
uv run pytest tests/test_settings.py

# Run with markers
uv run pytest -m unit
```

### Code Quality

```bash
# Format code with black
uv run black .

# Check formatting
uv run black --check .

# Lint with flake8
uv run flake8 .

# Type check with mypy
uv run mypy .

# Run all checks
uv run black --check . && uv run flake8 . && uv run mypy .
```

### Django Management Commands

```bash
# Create migrations
uv run python manage.py makemigrations

# Apply migrations
uv run python manage.py migrate

# Create superuser
uv run python manage.py createsuperuser

# Run Django shell
uv run python manage.py shell

# Check deployment readiness
uv run python manage.py check --deploy
```

## Project Structure

```
backend/
├── trading_system/          # Django project
│   ├── __init__.py
│   ├── settings.py         # Django settings
│   ├── urls.py             # URL routing
│   ├── asgi.py             # ASGI configuration
│   ├── wsgi.py             # WSGI configuration
│   ├── celery.py           # Celery configuration
│   └── routing.py          # WebSocket routing
├── tests/                  # Test files
├── logs/                   # Log files
├── config/                 # Configuration files
├── manage.py               # Django management script
├── pyproject.toml          # Project dependencies and config
├── setup.cfg               # Flake8 configuration
├── pytest.ini              # Pytest configuration
└── .env.example            # Environment variables template
```

## Configuration

### Environment Variables

See `.env.example` for all available environment variables.

Key variables:

- `DJANGO_SECRET_KEY`: Django secret key
- `DJANGO_DEBUG`: Debug mode (True/False)
- `POSTGRES_*`: PostgreSQL connection settings
- `REDIS_URL`: Redis connection URL
- `CELERY_BROKER_URL`: Celery broker URL
- `AWS_*`: AWS credentials for S3/Athena

### Django Settings

The settings are configured for:

- PostgreSQL database
- Redis caching and sessions
- Celery task queue
- Django Channels WebSocket
- Django REST Framework API
- Security settings for production

## Testing

Tests are organized by type using pytest markers:

- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.slow`: Slow running tests

Coverage reports are generated in `htmlcov/` directory.

## Code Quality Standards

- **Line Length**: 100 characters (black, flake8)
- **Type Hints**: Required for all functions (mypy)
- **Docstrings**: Required for all public functions and classes
- **Test Coverage**: Aim for >80% coverage

## Next Steps

1. Create Django apps for different modules (accounts, strategies, orders, etc.)
2. Implement database models
3. Create API endpoints
4. Set up WebSocket consumers
5. Implement Celery tasks
6. Add authentication and authorization
