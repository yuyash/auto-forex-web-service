# Database Migrations Guide

This document explains how database migrations work in both development and production environments for the Auto Forex Trading System.

## Overview

Database migrations are **automatically handled** in both development and production environments. Django's migration system ensures that your database schema stays in sync with your models.

## How Migrations Work

### 1. Creating Migrations (Development)

When you modify Django models, create migrations:

```bash
cd backend
python manage.py makemigrations
```

This generates migration files in `backend/<app>/migrations/` directories.

### 2. Applying Migrations

#### Local Development

```bash
cd backend
python manage.py migrate
```

#### Docker Development

Migrations run automatically when the backend container starts:

```yaml
command: >
  sh -c "python manage.py migrate &&
         python manage.py collectstatic --noinput &&
         daphne -b 0.0.0.0 -p 8000 trading_system.asgi:application"
```

#### Production

Migrations are applied automatically during deployment:

1. **GitHub Actions** builds a Docker image with your latest code and migrations
2. **Docker image** is pushed to DockerHub
3. **Production server** pulls the new image
4. **Backend container** starts and runs migrations before starting the application

## Production Deployment Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Developer pushes code to main branch                         │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. GitHub Actions CI/CD Pipeline                                │
│    - Builds Docker image with latest code & migrations          │
│    - Pushes image to DockerHub                                  │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Production Server Deployment                                 │
│    - Pulls latest image from DockerHub                          │
│    - Stops old containers (docker compose down)                 │
│    - Starts new containers (docker compose up -d)               │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Backend Container Startup                                    │
│    - Waits for PostgreSQL to be healthy                         │
│    - Runs: python manage.py migrate                             │
│    - Runs: python manage.py collectstatic --noinput             │
│    - Starts: daphne (ASGI server)                               │
└─────────────────────────────────────────────────────────────────┘
```

## Migration Files

Current migrations in the system:

### accounts app

- `0001_initial.py` - User, UserSettings, UserSession, BlockedIP, OandaAccount models

### trading app

- `0001_initial.py` - Strategy, StrategyState, Order, Position, Trade models
- `0002_add_event_logging_models.py` - Event, Notification models
- `0003_backtest_backtestresult_and_more.py` - Backtest, BacktestResult models

## Checking Migration Status

### Local Development

```bash
cd backend
python manage.py showmigrations
```

### Production

SSH into the production server and run:

```bash
cd /path/to/deployment
docker exec forex_backend python manage.py showmigrations
```

## Database Schema

After all migrations are applied, the following tables exist:

### User Management

- `users` - Extended Django user model
- `user_settings` - User preferences and defaults
- `user_sessions` - Session tracking for security
- `blocked_ips` - IP blocking for security

### Trading

- `oanda_accounts` - OANDA trading accounts
- `strategies` - Trading strategy configurations
- `strategy_states` - Runtime state for active strategies
- `orders` - Trading orders
- `positions` - Open trading positions
- `trades` - Completed trade records

### Backtesting

- `backtests` - Backtest configurations and execution tracking
- `backtest_results` - Performance metrics and results

### Event Logging

- `events` - System event log (trading, system, security, admin)
- `notifications` - Admin notifications

### Django System Tables

- `django_migrations` - Migration history
- `django_session` - Session data
- `django_admin_log` - Admin action log
- `django_content_type` - Content type registry
- `auth_*` - Django authentication tables
- `django_celery_beat_*` - Celery Beat scheduler tables

## Troubleshooting

### Migration Conflicts

If you encounter migration conflicts:

```bash
# Show migration status
python manage.py showmigrations

# If needed, fake a migration (use with caution)
python manage.py migrate --fake <app_name> <migration_name>

# Or squash migrations
python manage.py squashmigrations <app_name> <start_migration> <end_migration>
```

### Rolling Back Migrations

To roll back to a specific migration:

```bash
python manage.py migrate <app_name> <migration_name>
```

### Production Migration Failures

If migrations fail in production:

1. Check the backend container logs:

   ```bash
   docker logs forex_backend
   ```

2. Access the container and run migrations manually:

   ```bash
   docker exec -it forex_backend python manage.py migrate
   ```

3. Check database connectivity:
   ```bash
   docker exec -it forex_backend python manage.py dbshell
   ```

## Best Practices

1. **Always test migrations locally** before pushing to production
2. **Review migration files** to ensure they do what you expect
3. **Backup the database** before applying migrations in production
4. **Use migration dependencies** to ensure proper ordering
5. **Avoid data migrations** in the same file as schema migrations
6. **Test rollback procedures** to ensure they work correctly

## Zero-Downtime Migrations

For production systems that require zero downtime:

1. **Backward-compatible changes first**: Add new columns as nullable
2. **Deploy code**: Deploy application code that works with both old and new schema
3. **Run migrations**: Apply migrations to add new columns
4. **Backfill data**: Populate new columns with data
5. **Deploy code again**: Deploy code that uses new columns
6. **Clean up**: Remove old columns in a subsequent migration

## Manual Migration in Production

If you need to run migrations manually in production:

```bash
# SSH into production server
ssh user@production-server

# Navigate to deployment directory
cd /path/to/deployment

# Run migrations in the backend container
docker exec forex_backend python manage.py migrate

# Or enter the container and run commands
docker exec -it forex_backend bash
python manage.py migrate
python manage.py showmigrations
exit
```

## Environment-Specific Considerations

### Development

- Database: Local PostgreSQL (localhost:5432)
- Migrations: Run manually or via docker-compose
- Data: Can be reset/recreated easily

### Production

- Database: Docker PostgreSQL (postgres:5432)
- Migrations: Run automatically on container startup
- Data: Persistent volumes, requires careful handling

## Related Files

- `backend/accounts/models.py` - User and account models
- `backend/trading/models.py` - Trading models
- `backend/trading/backtest_models.py` - Backtest models
- `backend/trading/event_models.py` - Event logging models
- `docker-compose.yaml` - Development Docker configuration
- `docker-compose.prod.yaml` - Production Docker configuration
- `.github/workflows/build-and-deploy.yml` - CI/CD pipeline
- `backend/Dockerfile` - Backend Docker image definition

## Summary

✅ Migrations are **fully automated** in production
✅ No manual intervention required for normal deployments
✅ Migrations run before the application starts
✅ Database schema stays in sync with code automatically
✅ Safe rollback procedures are available if needed

For more information, see the [Django Migrations Documentation](https://docs.djangoproject.com/en/5.2/topics/migrations/).
