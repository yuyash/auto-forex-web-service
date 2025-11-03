# Production Scripts

This directory contains production-ready scripts for managing the Forex Trading System. These scripts are designed to be copied to the production server and used instead of the Makefile.

## Prerequisites

- Docker and Docker Compose installed
- `.env` file configured with production settings
- Services running via `docker-compose.yaml`

## Important Notes

- **Scripts can be run from any directory** - they automatically find the project root
- All scripts change to the project root directory before executing commands
- You can run scripts from within the `scripts/` directory or from the project root

## Scripts Overview

### Deployment

#### `deploy.sh`

Complete deployment script that handles the full deployment process.

```bash
./scripts/deploy.sh
```

This script:

- Checks for `.env` file
- Pulls latest Docker images
- Stops existing services
- Starts new services
- Waits for database to be ready
- Runs migrations
- Collects static files
- Initializes system settings
- Shows service status

### User Management

#### `manage-registration.sh`

Enable or disable user registration.

```bash
# Enable registration
./scripts/manage-registration.sh enable

# Disable registration
./scripts/manage-registration.sh disable

# Check status
./scripts/manage-registration.sh status
```

#### `manage-login.sh`

Enable or disable user login.

```bash
# Enable login
./scripts/manage-login.sh enable

# Disable login
./scripts/manage-login.sh disable

# Check status
./scripts/manage-login.sh status
```

### Database Management

#### `backup.sh`

Create a database backup.

```bash
./scripts/backup.sh
```

Backups are stored in `./backups/` directory with timestamp.

Environment variables:

- `BACKUP_DIR`: Backup directory (default: `./backups`)
- `BACKUP_RETENTION_DAYS`: Days to keep backups (default: 30)

#### `restore.sh`

Restore database from a backup.

```bash
# List available backups
./scripts/restore.sh

# Restore specific backup
./scripts/restore.sh ./backups/backup_20250103_120000.sql.gz
```

### Monitoring

#### `health-check.sh`

Comprehensive health check for all services.

```bash
./scripts/health-check.sh
```

Checks:

- Service status (postgres, redis, backend, celery, frontend, nginx)
- PostgreSQL connectivity
- Redis connectivity
- Backend API health endpoint
- Disk space usage
- Docker volumes
- Resource usage (CPU, memory, network)

#### `logs.sh`

View logs from services.

```bash
# View all logs (last 100 lines)
./scripts/logs.sh all

# Follow backend logs
./scripts/logs.sh backend -f

# View last 50 lines of celery logs
./scripts/logs.sh celery --tail 50

# Available services: all, backend, celery, beat, frontend, nginx, postgres, redis
```

### Django Management

#### `manage.sh`

Wrapper for Django management commands.

```bash
# Run migrations
./scripts/manage.sh migrate

# Create superuser
./scripts/manage.sh createsuperuser

# Open Django shell
./scripts/manage.sh shell

# Collect static files
./scripts/manage.sh collectstatic

# Any Django management command
./scripts/manage.sh [command] [args...]
```

## Environment Variables

All scripts support the following environment variables:

- `COMPOSE_FILE`: Docker Compose file to use (default: `docker-compose.yaml`)
- `PROJECT_NAME`: Project name (default: `forex-trading`)

Example:

```bash
COMPOSE_FILE=docker-compose.prod.yaml ./scripts/deploy.sh
```

### Service Management

#### `service.sh`

Quick service management commands.

```bash
# Start services
./scripts/service.sh start

# Stop services
./scripts/service.sh stop

# Restart services
./scripts/service.sh restart

# Check status
./scripts/service.sh status

# Pull latest images
./scripts/service.sh pull

# Clean up (remove containers, volumes, images)
./scripts/service.sh clean
```

## GitHub Actions Integration

The deployment workflow automatically copies the scripts directory to the production server:

```yaml
- name: Deploy to production server
  run: |
    # Copy scripts directory
    scp -P ${SSH_PORT} -r scripts ${SERVER_USER}@${SERVER_HOST}:${DEPLOY_PATH}/

    # Make scripts executable
    ssh -p ${SSH_PORT} ${SERVER_USER}@${SERVER_HOST} << EOF
      cd ${DEPLOY_PATH}
      chmod +x scripts/*.sh

      # Run deployment
      ./scripts/deploy.sh
    EOF
```

## Making Scripts Executable

After copying scripts to the server, make them executable:

```bash
chmod +x scripts/*.sh
```

## Production Best Practices

1. **Regular Backups**: Schedule `backup.sh` to run daily via cron

   ```bash
   0 2 * * * /path/to/scripts/backup.sh
   ```

2. **Health Monitoring**: Run `health-check.sh` periodically

   ```bash
   */15 * * * * /path/to/scripts/health-check.sh
   ```

3. **Log Rotation**: Monitor log sizes and rotate as needed

4. **Security**:

   - Keep scripts in a secure directory
   - Limit access to authorized users only
   - Never commit `.env` files to version control

5. **Testing**: Test scripts in a staging environment before production

## Troubleshooting

### Services not starting

```bash
# Check logs
./scripts/logs.sh all

# Check service status
docker compose ps

# Restart services
docker compose restart
```

### Database connection issues

```bash
# Check PostgreSQL
docker compose exec postgres pg_isready -U postgres

# Check database logs
./scripts/logs.sh postgres
```

### Permission issues

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Check file ownership
ls -la scripts/
```

## Support

For issues or questions, refer to the main project documentation or contact the development team.
