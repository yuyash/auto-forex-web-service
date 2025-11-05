# Docker Setup Guide

This guide explains how to deploy the Auto Forex Trader using Docker Compose.

## Prerequisites

- Docker Engine 20.10+ installed
- Docker Compose 2.0+ installed
- At least 4GB RAM available
- 20GB disk space
- Domain name with DNS configured (for SSL)
- Ports 80 and 443 available

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd auto-forex-trading-system
```

### 2. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit the .env file with your configuration
nano .env
```

**Required Variables:**

- `DB_PASSWORD`: Strong password for PostgreSQL
- `REDIS_PASSWORD`: Strong password for Redis
- `SECRET_KEY`: Django secret key (50+ characters)
- `ENCRYPTION_KEY`: Fernet encryption key for API tokens

**Generate Encryption Key:**

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Generate Django Secret Key:**

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

### 3. Build and Start Services

```bash
# Build all Docker images
docker-compose build

# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

### 4. Initialize the Database

```bash
# Run database migrations
docker-compose exec backend python manage.py migrate

# Create superuser account
docker-compose exec backend python manage.py createsuperuser

# Collect static files
docker-compose exec backend python manage.py collectstatic --noinput
```

### 5. Configure SSL Certificates

**For Development (HTTP only):**
The system will work on HTTP without SSL certificates.

**For Production (HTTPS with Let's Encrypt):**

```bash
# Update nginx/conf.d/default.conf with your domain name
# Replace 'your-domain.com' with your actual domain

# Obtain SSL certificate
docker-compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email \
  -d yourdomain.com \
  -d www.yourdomain.com

# Reload nginx to use the new certificates
docker-compose exec nginx nginx -s reload
```

### 6. Access the Application

- **Frontend**: https://yourdomain.com (or http://localhost if no SSL)
- **Backend API**: https://yourdomain.com/api/
- **Admin Panel**: https://yourdomain.com/api/admin/
- **WebSocket**: wss://yourdomain.com/ws/

## Service Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Internet (Port 443)                   │
└────────────────────────┬────────────────────────────────┘
                         │
                    ┌────▼────┐
                    │  Nginx  │  (Reverse Proxy + SSL)
                    └────┬────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   ┌────▼────┐     ┌────▼────┐     ┌────▼────┐
   │ Backend │     │Frontend │     │WebSocket│
   │(Django) │     │ (React) │     │(Channels)│
   └────┬────┘     └─────────┘     └────┬────┘
        │                                │
        └────────────┬───────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
   ┌────▼────┐  ┌───▼───┐   ┌───▼────┐
   │Postgres │  │ Redis │   │ Celery │
   │   DB    │  │ Cache │   │Workers │
   └─────────┘  └───────┘   └────────┘
```

## Docker Services

### Core Services

1. **postgres**: PostgreSQL 17 database

   - Port: 5432
   - Volume: `postgres_data`
   - Health check enabled

2. **redis**: Redis 7 cache and message broker

   - Port: 6379
   - Volume: `redis_data`
   - Persistence enabled (AOF)

3. **backend**: Django application server

   - Port: 8000
   - Runs with Daphne (ASGI server)
   - Handles REST API and WebSocket connections

4. **celery**: Background task worker

   - Processes market data streaming
   - Executes trading strategies
   - Runs backtests
   - Handles scheduled tasks

5. **celery-beat**: Task scheduler

   - Schedules periodic tasks
   - Account balance updates
   - Health checks
   - ATR calculations

6. **frontend**: React application

   - Built with Vite
   - Served by internal Nginx

7. **nginx**: Reverse proxy and SSL termination

   - Ports: 80 (HTTP), 443 (HTTPS)
   - Rate limiting enabled
   - WebSocket proxy support

8. **certbot**: SSL certificate management
   - Automatic certificate renewal
   - Runs every 12 hours

## Common Commands

### Service Management

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart a specific service
docker-compose restart backend

# View logs
docker-compose logs -f backend
docker-compose logs -f celery

# View all logs
docker-compose logs -f
```

### Database Operations

```bash
# Run migrations
docker-compose exec backend python manage.py migrate

# Create database backup
docker-compose exec postgres pg_dump -U postgres forex_trading > backup.sql

# Restore database backup
docker-compose exec -T postgres psql -U postgres forex_trading < backup.sql

# Access PostgreSQL shell
docker-compose exec postgres psql -U postgres -d forex_trading
```

### Application Management

```bash
# Create superuser
docker-compose exec backend python manage.py createsuperuser

# Run Django shell
docker-compose exec backend python manage.py shell

# Collect static files
docker-compose exec backend python manage.py collectstatic --noinput

# Run tests
docker-compose exec backend pytest
```

### Monitoring

```bash
# Check service health
docker-compose ps

# View resource usage
docker stats

# Check logs for errors
docker-compose logs --tail=100 backend | grep ERROR
docker-compose logs --tail=100 celery | grep ERROR
```

## Troubleshooting

### Services Won't Start

```bash
# Check service logs
docker-compose logs backend
docker-compose logs postgres
docker-compose logs redis

# Verify environment variables
docker-compose config

# Rebuild images
docker-compose build --no-cache
docker-compose up -d
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test database connection
docker-compose exec backend python manage.py dbshell

# Check database logs
docker-compose logs postgres
```

### SSL Certificate Issues

```bash
# Check certificate files exist
ls -la certbot/conf/live/yourdomain.com/

# Test certificate renewal
docker-compose run --rm certbot renew --dry-run

# Check nginx configuration
docker-compose exec nginx nginx -t

# Reload nginx
docker-compose exec nginx nginx -s reload
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Increase Celery workers
# Edit docker-compose.yaml: --concurrency=8

# Check database performance
docker-compose exec postgres psql -U postgres -d forex_trading -c "SELECT * FROM pg_stat_activity;"
```

## Production Deployment

### Security Checklist

- [ ] Set `DEBUG=False` in .env
- [ ] Use strong passwords for DB_PASSWORD and REDIS_PASSWORD
- [ ] Generate unique SECRET_KEY and ENCRYPTION_KEY
- [ ] Configure firewall to allow only ports 80 and 443
- [ ] Set up DDNS for dynamic IP addresses
- [ ] Configure port forwarding on router
- [ ] Enable SSL with Let's Encrypt
- [ ] Set up automated backups
- [ ] Configure monitoring and alerting
- [ ] Review nginx rate limiting settings
- [ ] Set ALLOWED_HOSTS to your domain only

### Backup Strategy

```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"

# Database backup
docker-compose exec -T postgres pg_dump -U postgres forex_trading | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Volume backup
docker run --rm -v forex_postgres_data:/data -v $BACKUP_DIR:/backup alpine tar czf /backup/postgres_volume_$DATE.tar.gz -C /data .
docker run --rm -v forex_redis_data:/data -v $BACKUP_DIR:/backup alpine tar czf /backup/redis_volume_$DATE.tar.gz -C /data .

# Keep only last 7 days
find $BACKUP_DIR -name "*.gz" -mtime +7 -delete
EOF

chmod +x backup.sh

# Add to crontab for daily backups
crontab -e
# Add: 0 2 * * * /path/to/backup.sh
```

### Monitoring Setup

```bash
# View real-time logs
docker-compose logs -f --tail=100

# Set up log rotation
# Edit /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}

# Restart Docker daemon
sudo systemctl restart docker
```

## Updating the Application

```bash
# Pull latest code
git pull origin main

# Rebuild images
docker-compose build

# Stop services
docker-compose down

# Start with new images
docker-compose up -d

# Run migrations
docker-compose exec backend python manage.py migrate

# Collect static files
docker-compose exec backend python manage.py collectstatic --noinput
```

## Scaling

### Horizontal Scaling

```bash
# Scale Celery workers
docker-compose up -d --scale celery=4

# Scale backend instances (requires load balancer)
docker-compose up -d --scale backend=3
```

### Resource Limits

Edit `docker-compose.yaml` to add resource limits:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 2G
        reservations:
          cpus: "1"
          memory: 1G
```

## Support

For issues and questions:

- Check logs: `docker-compose logs -f`
- Review documentation in `/docs`
- Check GitHub issues
- Contact support team

## License

See LICENSE file for details.
