# Environment Variables Reference

This document describes all environment variables used in the Auto Forex Trading System.

## Overview

The system uses a single `.env` file in the project root for both development and production. This simplifies configuration and reduces the number of variables you need to manage.

## Required Variables

These variables MUST be set for the system to function:

### Database Configuration

| Variable      | Description              | Default         | Example              |
| ------------- | ------------------------ | --------------- | -------------------- |
| `DB_NAME`     | PostgreSQL database name | `forex_trading` | `forex_trading`      |
| `DB_USER`     | PostgreSQL username      | `postgres`      | `postgres`           |
| `DB_PASSWORD` | PostgreSQL password      | **Required**    | `secure_password123` |
| `DB_HOST`     | PostgreSQL host          | `postgres`      | `postgres` (Docker)  |
| `DB_PORT`     | PostgreSQL port          | `5432`          | `5432`               |

**Notes:**

- In Docker, `DB_HOST` should be `postgres` (the service name)
- For local development, use `localhost`
- `DB_PASSWORD` has no default and must be set

**⚠️ IMPORTANT - Password Management:**

PostgreSQL stores its password in the data volume when first initialized. Once set, changing `DB_PASSWORD` in `.env` alone won't update the actual database password. You must update both:

1. Update `.env` file with new password
2. Update PostgreSQL: `docker exec forex_postgres psql -U postgres -c "ALTER USER postgres PASSWORD 'new_password';"`
3. Restart services: `docker compose restart backend celery celery-beat`

The deployment script (`deploy.sh`) automatically syncs the password on each deployment to prevent mismatches.

### Django Configuration

| Variable        | Description                      | Default               | Example                                 |
| --------------- | -------------------------------- | --------------------- | --------------------------------------- |
| `SECRET_KEY`    | Django secret key (min 50 chars) | **Required**          | `django-insecure-abc123...`             |
| `DEBUG`         | Enable debug mode                | `False`               | `True` (dev), `False` (prod)            |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts    | `localhost,127.0.0.1` | `example.com,www.example.com,localhost` |

**Notes:**

- Generate `SECRET_KEY` with: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- NEVER set `DEBUG=True` in production
- `ALLOWED_HOSTS` must include all domains/IPs that will access the application

### Security Configuration

| Variable         | Description                          | Default      | Example                             |
| ---------------- | ------------------------------------ | ------------ | ----------------------------------- |
| `ENCRYPTION_KEY` | Fernet key for encrypting API tokens | **Required** | `abc123def456...` (44 chars base64) |

**Notes:**

- Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Used to encrypt OANDA API tokens in the database
- Minimum 32 characters, must be a valid Fernet key

## Optional Variables

These variables have sensible defaults but can be customized:

### Redis Configuration

| Variable         | Description               | Default                | Example                 |
| ---------------- | ------------------------- | ---------------------- | ----------------------- |
| `REDIS_URL`      | Redis connection URL      | `redis://redis:6379/0` | `redis://redis:6379/0`  |
| `REDIS_PASSWORD` | Redis password (optional) | `` (empty, no auth)    | `secure_redis_password` |

**Notes:**

- If `REDIS_PASSWORD` is set, Redis will require authentication
- In Docker, Redis host should be `redis` (the service name)
- For local development, use `redis://localhost:6379/0`

### Celery Configuration

| Variable                | Description               | Default                | Example                |
| ----------------------- | ------------------------- | ---------------------- | ---------------------- |
| `CELERY_BROKER_URL`     | Celery message broker URL | `redis://redis:6379/0` | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery result backend URL | `redis://redis:6379/0` | `redis://redis:6379/0` |

**Notes:**

- Should match `REDIS_URL` in most cases
- If `REDIS_PASSWORD` is set, use format: `redis://:password@redis:6379/0`

### OANDA API Configuration

| Variable             | Description                 | Default                            | Example                            |
| -------------------- | --------------------------- | ---------------------------------- | ---------------------------------- |
| `OANDA_PRACTICE_API` | OANDA practice API endpoint | `https://api-fxpractice.oanda.com` | `https://api-fxpractice.oanda.com` |
| `OANDA_LIVE_API`     | OANDA live API endpoint     | `https://api-fxtrade.oanda.com`    | `https://api-fxtrade.oanda.com`    |

**Notes:**

- These are the official OANDA API endpoints
- Usually don't need to be changed
- API tokens are stored per-user in the database (encrypted)

### AWS Configuration (Optional - for Backtesting)

| Variable                | Description           | Default     | Example                    |
| ----------------------- | --------------------- | ----------- | -------------------------- |
| `AWS_ACCESS_KEY_ID`     | AWS access key ID     | `` (empty)  | `AKIAIOSFODNN7EXAMPLE`     |
| `AWS_SECRET_ACCESS_KEY` | AWS secret access key | `` (empty)  | `wJalrXUtnFEMI/K7MDENG...` |
| `AWS_REGION`            | AWS region            | `us-east-1` | `us-east-1`                |
| `AWS_S3_BUCKET`         | S3 bucket for data    | `` (empty)  | `forex-historical-data`    |

**Notes:**

- Only required if using AWS S3/Athena for backtesting
- Can be left empty for basic trading functionality
- Ensure IAM user has S3 and Athena permissions

### Docker Configuration (Production Only)

| Variable             | Description              | Default      | Example              |
| -------------------- | ------------------------ | ------------ | -------------------- |
| `DOCKERHUB_USERNAME` | DockerHub username       | **Required** | `myusername`         |
| `DOCKERHUB_TOKEN`    | DockerHub access token   | **Required** | `dckr_pat_abc123...` |
| `VERSION`            | Docker image version tag | `latest`     | `latest`, `v1.0.0`   |

**Notes:**

- Only needed for production deployments using pre-built images
- Not required for local development (builds from source)

### SSL/Domain Configuration (Production Only)

| Variable | Description             | Default      | Example               |
| -------- | ----------------------- | ------------ | --------------------- |
| `DOMAIN` | Your domain name        | **Required** | `trading.example.com` |
| `EMAIL`  | Email for Let's Encrypt | **Required** | `admin@example.com`   |

**Notes:**

- Only needed for production with SSL/HTTPS
- Used by Certbot for SSL certificate generation

## Environment-Specific Configurations

### Development (.env)

```bash
# Database
DB_NAME=forex_trading
DB_USER=postgres
DB_PASSWORD=dev_password_123
DB_HOST=postgres
DB_PORT=5432

# Django
SECRET_KEY=django-insecure-dev-key-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Redis
REDIS_PASSWORD=

# Security
ENCRYPTION_KEY=your-dev-encryption-key-here

# OANDA
OANDA_PRACTICE_API=https://api-fxpractice.oanda.com
OANDA_LIVE_API=https://api-fxtrade.oanda.com
```

### Production (.env)

```bash
# Database
DB_NAME=forex_trading
DB_USER=postgres
DB_PASSWORD=super_secure_production_password_here
DB_HOST=postgres
DB_PORT=5432

# Django
SECRET_KEY=production-secret-key-min-50-chars-random-string
DEBUG=False
ALLOWED_HOSTS=trading.example.com,www.trading.example.com

# Redis
REDIS_PASSWORD=secure_redis_password_here

# Security
ENCRYPTION_KEY=production-encryption-key-32-chars-minimum

# OANDA
OANDA_PRACTICE_API=https://api-fxpractice.oanda.com
OANDA_LIVE_API=https://api-fxtrade.oanda.com

# Docker
DOCKERHUB_USERNAME=myusername
DOCKERHUB_TOKEN=your_docker_hub_token
VERSION=latest

# SSL
DOMAIN=trading.example.com
EMAIL=admin@example.com
```

## How Variables Are Used

### In Docker Compose

Variables from `.env` are automatically loaded by Docker Compose and passed to containers:

```yaml
environment:
  DB_NAME: ${DB_NAME:-forex_trading}
  DB_USER: ${DB_USER:-postgres}
  DB_PASSWORD: ${DB_PASSWORD:?Database password required}
```

Syntax:

- `${VAR:-default}`: Use `VAR` if set, otherwise use `default`
- `${VAR:?error}`: Use `VAR` if set, otherwise show error and fail

### In Django Settings

Variables are read using `os.getenv()`:

```python
DATABASES = {
    "default": {
        "NAME": os.getenv("DB_NAME", "forex_trading"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", "postgres"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}
```

## Security Best Practices

1. **Never commit `.env` to version control**

   - `.env` is in `.gitignore`
   - Use `.env.example` as a template

2. **Use strong passwords**

   - Database: min 16 characters, mixed case, numbers, symbols
   - Redis: min 16 characters
   - Generate with: `openssl rand -base64 32`

3. **Rotate secrets regularly**

   - Change passwords every 90 days
   - Regenerate `SECRET_KEY` and `ENCRYPTION_KEY` periodically

4. **Limit access**

   - Only authorized personnel should have access to `.env`
   - Use different credentials for dev/staging/production

5. **Use environment-specific values**
   - Never use development credentials in production
   - Use different `SECRET_KEY` for each environment

## Troubleshooting

### "Database password required" error

**Problem**: Docker Compose fails with "required variable is missing a value"

**Solution**: Ensure `DB_PASSWORD` is set in `.env` file

### "Connection refused" errors

**Problem**: Services can't connect to database or Redis

**Solution**:

- In Docker: Use service names (`postgres`, `redis`)
- Locally: Use `localhost`
- Check `DB_HOST` and `REDIS_URL` settings

### "Invalid ENCRYPTION_KEY" error

**Problem**: Can't decrypt API tokens

**Solution**:

- Ensure `ENCRYPTION_KEY` is a valid Fernet key
- Generate new key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Note: Changing the key will invalidate existing encrypted data

### "DisallowedHost" error

**Problem**: Django rejects requests with "Invalid HTTP_HOST header"

**Solution**: Add the domain/IP to `ALLOWED_HOSTS` in `.env`

## Migration from Old Variables

If you're upgrading from an older version that used different variable names:

| Old Variable           | New Variable    | Notes                   |
| ---------------------- | --------------- | ----------------------- |
| `POSTGRES_DB`          | `DB_NAME`       | Simplified naming       |
| `POSTGRES_USER`        | `DB_USER`       | Simplified naming       |
| `POSTGRES_PASSWORD`    | `DB_PASSWORD`   | Simplified naming       |
| `POSTGRES_HOST`        | `DB_HOST`       | Simplified naming       |
| `POSTGRES_PORT`        | `DB_PORT`       | Simplified naming       |
| `DJANGO_SECRET_KEY`    | `SECRET_KEY`    | Removed DJANGO\_ prefix |
| `DJANGO_DEBUG`         | `DEBUG`         | Removed DJANGO\_ prefix |
| `DJANGO_ALLOWED_HOSTS` | `ALLOWED_HOSTS` | Removed DJANGO\_ prefix |

**Migration steps:**

1. Copy `.env.example` to `.env`
2. Transfer values from old variables to new ones
3. Test locally with `docker compose up`
4. Deploy to production

## Additional Resources

- [Django Settings Documentation](https://docs.djangoproject.com/en/5.2/ref/settings/)
- [Docker Compose Environment Variables](https://docs.docker.com/compose/environment-variables/)
- [PostgreSQL Environment Variables](https://www.postgresql.org/docs/current/libpq-envars.html)
- [Redis Configuration](https://redis.io/docs/management/config/)
