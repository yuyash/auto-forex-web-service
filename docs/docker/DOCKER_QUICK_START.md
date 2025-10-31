# Docker Quick Start Guide

## Prerequisites

- Docker & Docker Compose installed
- Domain name configured (for production)
- Ports 80 and 443 available

## Development Setup (5 minutes)

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Generate required keys
python3 -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(50))" >> .env

# 3. Set passwords in .env
# Edit .env and set:
# - DB_PASSWORD
# - REDIS_PASSWORD

# 4. Build and start
docker-compose build
docker-compose up -d

# 5. Initialize database
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser

# 6. Access application
# Frontend: http://localhost
# Backend API: http://localhost/api/
# Admin: http://localhost/api/admin/
```

## Production Setup (with SSL)

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with production values

# 2. Set domain and email
export DOMAIN=yourdomain.com
export EMAIL=your-email@example.com

# 3. Run SSL setup script
./init-letsencrypt.sh

# 4. Start all services
docker-compose up -d

# 5. Initialize database
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser

# 6. Access application
# https://yourdomain.com
```

## Essential Commands

```bash
# View logs
docker-compose logs -f backend

# Restart service
docker-compose restart backend

# Stop all
docker-compose down

# Backup database
docker-compose exec postgres pg_dump -U postgres forex_trading > backup.sql

# Run tests
docker-compose exec backend pytest
```

## Troubleshooting

**Services won't start:**

```bash
docker-compose logs
docker-compose ps
```

**Database issues:**

```bash
docker-compose logs postgres
docker-compose exec backend python manage.py dbshell
```

**SSL certificate issues:**

```bash
docker-compose logs certbot
docker-compose exec nginx nginx -t
```

## Service Ports

- **80**: HTTP (redirects to HTTPS)
- **443**: HTTPS (main access)
- **5432**: PostgreSQL (internal)
- **6379**: Redis (internal)
- **8000**: Django backend (internal)

## Next Steps

1. Configure OANDA API credentials in user settings
2. Add trading accounts via the web interface
3. Configure trading strategies
4. Set up monitoring and alerts
5. Configure automated backups

For detailed documentation, see `DOCKER_SETUP.md`
