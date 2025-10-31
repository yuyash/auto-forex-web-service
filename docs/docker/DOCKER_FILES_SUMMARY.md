# Docker Configuration Files Summary

This document provides an overview of all Docker-related files created for the Auto Forex Trading System.

## File Structure

```
.
├── docker-compose.yaml              # Main orchestration file
├── .env.example                     # Environment variables template
├── init-letsencrypt.sh             # SSL certificate setup script
├── Makefile                        # Convenient command shortcuts
├── DOCKER_SETUP.md                 # Comprehensive setup guide
├── DOCKER_QUICK_START.md           # Quick reference guide
│
├── backend/
│   ├── Dockerfile                  # Backend container definition
│   └── .dockerignore              # Files to exclude from build
│
├── frontend/
│   ├── Dockerfile                  # Frontend container definition (multi-stage)
│   ├── nginx.conf                 # Frontend nginx config
│   └── .dockerignore              # Files to exclude from build
│
└── nginx/
    ├── Dockerfile                  # Nginx container definition
    ├── nginx.conf                 # Main nginx configuration
    └── conf.d/
        └── default.conf           # Server block configuration
```

## File Descriptions

### docker-compose.yaml

**Purpose**: Orchestrates all services for the application

**Services Defined**:

1. **postgres** - PostgreSQL 17 database
2. **redis** - Redis 7 cache and message broker
3. **backend** - Django application (Python 3.13)
4. **celery** - Background task worker
5. **celery-beat** - Task scheduler
6. **frontend** - React application
7. **nginx** - Reverse proxy with SSL
8. **certbot** - SSL certificate management

**Key Features**:

- Health checks for critical services
- Named volumes for data persistence
- Custom network for service isolation
- Environment variable configuration
- Automatic service dependencies

### Backend Dockerfile

**Base Image**: python:3.13-slim

**Key Steps**:

1. Install system dependencies (gcc, postgresql-client)
2. Install uv for dependency management
3. Install Python dependencies from pyproject.toml
4. Copy application code
5. Collect static files
6. Run migrations and start Daphne ASGI server

**Exposed Port**: 8000

### Frontend Dockerfile

**Multi-stage Build**:

**Stage 1 - Builder** (node:20-alpine):

1. Install npm dependencies
2. Build React application with Vite
3. Generate optimized production bundle

**Stage 2 - Server** (nginx:alpine):

1. Copy built files from builder
2. Configure nginx for SPA routing
3. Enable gzip compression
4. Set security headers

**Exposed Port**: 80

### Nginx Dockerfile

**Base Image**: nginx:alpine

**Key Features**:

- Installs certbot for SSL management
- Custom nginx configuration
- SSL certificate directories
- Exposes ports 80 and 443

### Nginx Configuration Files

**nginx.conf** (Main Configuration):

- Worker process settings
- Logging configuration
- Gzip compression
- Rate limiting zones (100 req/min for API, 5 req/min for login)

**conf.d/default.conf** (Server Blocks):

- HTTP to HTTPS redirect
- SSL/TLS configuration
- Reverse proxy to backend
- WebSocket proxy support
- Static file serving
- Rate limiting enforcement
- Security headers

### Environment Configuration

**.env.example**:
Template for all required environment variables:

- Database credentials
- Redis password
- Django secret key
- OANDA API endpoints
- AWS credentials (for backtesting)
- Encryption key
- SSL/domain configuration

### Helper Scripts

**init-letsencrypt.sh**:

- Automated SSL certificate setup
- Creates dummy certificates for initial nginx start
- Requests real certificates from Let's Encrypt
- Supports staging mode for testing
- Configurable domain and email

**Makefile**:
Convenient shortcuts for common operations:

- `make build` - Build images
- `make up` - Start services
- `make down` - Stop services
- `make logs` - View logs
- `make migrate` - Run migrations
- `make test` - Run tests
- `make backup` - Backup database
- `make ssl-init` - Initialize SSL
- And many more...

### Documentation Files

**DOCKER_SETUP.md**:

- Comprehensive deployment guide
- Service architecture diagram
- Common commands reference
- Troubleshooting section
- Production deployment checklist
- Backup and monitoring strategies

**DOCKER_QUICK_START.md**:

- Quick reference for common tasks
- 5-minute development setup
- Production setup with SSL
- Essential commands
- Troubleshooting tips

## Docker Ignore Files

### backend/.dockerignore

Excludes from backend image:

- Python cache files (**pycache**, \*.pyc)
- Virtual environments
- Test artifacts
- IDE files
- Logs and databases
- Documentation

### frontend/.dockerignore

Excludes from frontend image:

- node_modules
- Test coverage
- Build artifacts
- IDE files
- Environment files
- Documentation

## Network Architecture

```
Internet (Port 443)
        ↓
    Nginx Container
    (SSL Termination)
        ↓
    ┌───┴───┬────────┬─────────┐
    ↓       ↓        ↓         ↓
Backend Frontend WebSocket  Static
(Django) (React) (Channels) (Files)
    ↓
    ├─────────┬──────────┐
    ↓         ↓          ↓
PostgreSQL  Redis    Celery
```

## Volume Mounts

**Persistent Volumes**:

- `postgres_data` - Database files
- `redis_data` - Redis persistence
- `static_volume` - Django static files
- `media_volume` - User uploads

**Bind Mounts** (Development):

- `./backend:/app` - Live code reload
- `./config:/app/config` - Configuration files
- `./logs:/app/logs` - Application logs
- `./certbot/conf:/etc/letsencrypt` - SSL certificates
- `./certbot/www:/var/www/certbot` - ACME challenges

## Port Mappings

**External Ports** (exposed to host):

- 80 → nginx (HTTP, redirects to HTTPS)
- 443 → nginx (HTTPS)
- 5432 → postgres (development only)
- 6379 → redis (development only)

**Internal Ports** (container network only):

- 8000 → backend (Django/Daphne)
- 80 → frontend (internal nginx)

## Environment Variables

**Required**:

- `DB_PASSWORD` - PostgreSQL password
- `REDIS_PASSWORD` - Redis password
- `SECRET_KEY` - Django secret key (50+ chars)
- `ENCRYPTION_KEY` - Fernet key for API token encryption

**Optional with Defaults**:

- `DB_NAME` (default: forex_trading)
- `DB_USER` (default: postgres)
- `DEBUG` (default: False)
- `ALLOWED_HOSTS` (default: localhost,127.0.0.1)
- `OANDA_PRACTICE_API` (default: https://api-fxpractice.oanda.com)
- `OANDA_LIVE_API` (default: https://api-fxtrade.oanda.com)

## Security Features

1. **SSL/TLS Encryption**:

   - Let's Encrypt certificates
   - TLS 1.2 and 1.3 only
   - Strong cipher suites
   - HSTS enabled

2. **Rate Limiting**:

   - API: 100 requests/minute
   - Login: 5 requests/minute
   - Configurable burst limits

3. **Security Headers**:

   - X-Frame-Options: SAMEORIGIN
   - X-Content-Type-Options: nosniff
   - X-XSS-Protection: 1; mode=block
   - Strict-Transport-Security
   - Referrer-Policy

4. **Network Isolation**:

   - Custom Docker network
   - Internal service communication
   - Minimal port exposure

5. **Secrets Management**:
   - Environment variables
   - Encrypted API tokens
   - No hardcoded credentials

## Health Checks

**PostgreSQL**:

```yaml
test: ["CMD-SHELL", "pg_isready -U postgres -d forex_trading"]
interval: 10s
timeout: 5s
retries: 5
```

**Redis**:

```yaml
test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
interval: 10s
timeout: 3s
retries: 5
```

## Deployment Workflow

1. **Development**:

   ```bash
   make dev-setup
   make dev
   ```

2. **Production**:

   ```bash
   make prod-setup
   make ssl-init
   make build && make up
   make migrate && make superuser
   ```

3. **Updates**:
   ```bash
   git pull
   make build
   make down && make up
   make migrate
   ```

## Monitoring and Maintenance

**View Logs**:

```bash
make logs              # All services
make logs-backend      # Backend only
make logs-celery       # Celery only
```

**Health Check**:

```bash
make ps                # Service status
make stats             # Resource usage
make health            # Comprehensive check
```

**Backup**:

```bash
make backup            # Create database backup
make restore           # Restore from backup
```

**SSL Renewal**:

```bash
make ssl-renew         # Manual renewal
# Automatic renewal runs every 12 hours via certbot service
```

## Requirements Satisfied

This implementation satisfies the following requirements from the specification:

- **6.2**: Docker Compose configuration with all services
- **6.3**: Service communication and networking
- **6.4**: Data persistence with volumes
- **6.5**: Nginx exposed to host network only
- **14.1-14.5**: SSL/TLS encryption with Let's Encrypt
- **35.2**: Rate limiting configuration

## Next Steps

After Docker setup:

1. Configure environment variables in .env
2. Initialize SSL certificates (production)
3. Run database migrations
4. Create superuser account
5. Configure OANDA API credentials
6. Set up monitoring and backups
7. Configure firewall and port forwarding

## Support

For detailed instructions, see:

- `DOCKER_SETUP.md` - Comprehensive guide
- `DOCKER_QUICK_START.md` - Quick reference
- `Makefile` - Available commands (`make help`)
