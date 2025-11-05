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
