# Nginx Configuration Guide

This project uses different nginx configurations for development and production environments.

## Overview

- **Development**: HTTP only (no SSL certificates required)
- **Production**: HTTPS with SSL certificates via Let's Encrypt

## File Structure

```
nginx/
├── Dockerfile.dev          # Development Dockerfile (HTTP only)
├── Dockerfile.prod         # Production Dockerfile (with SSL support)
├── nginx.conf              # Main nginx configuration (shared)
└── conf.d/
    ├── dev.conf           # Development server config (HTTP)
    ├── prod.conf          # Production server config (HTTPS)
    └── default.conf       # Legacy config (can be removed)
```

## Development Environment

### Configuration

- Uses `Dockerfile.dev` and `dev.conf`
- HTTP only on port 80
- No SSL certificates needed
- Simpler setup for local development

### Usage

```bash
docker-compose up --build
```

Access the application at: `http://localhost`

## Production Environment

### Configuration

- Uses `Dockerfile.prod` and `prod.conf`
- HTTPS on port 443 (HTTP redirects to HTTPS)
- SSL certificates from Let's Encrypt
- Includes certbot for automatic certificate renewal

### Usage

```bash
docker-compose -f docker-compose.prod.yaml up --build
```

### SSL Certificate Setup

1. Update `nginx/conf.d/prod.conf` with your domain name:

   ```nginx
   ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
   ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
   ```

2. Run the Let's Encrypt initialization script:

   ```bash
   ./init-letsencrypt.sh
   ```

3. Certificates will auto-renew every 12 hours via the certbot container

## Key Differences

| Feature          | Development | Production |
| ---------------- | ----------- | ---------- |
| Protocol         | HTTP        | HTTPS      |
| Ports            | 80          | 80, 443    |
| SSL              | No          | Yes        |
| Certbot          | No          | Yes        |
| Security Headers | No          | Yes        |
| HSTS             | No          | Yes        |

## Common Configuration

Both environments share:

- Rate limiting for API endpoints
- WebSocket support
- Static file serving
- Media file serving
- Proxy settings for backend and frontend

## Switching Between Environments

The docker-compose files automatically use the correct configuration:

- `docker-compose.yaml` → Development (Dockerfile.dev)
- `docker-compose.prod.yaml` → Production (Dockerfile.prod)

No manual configuration changes needed!
