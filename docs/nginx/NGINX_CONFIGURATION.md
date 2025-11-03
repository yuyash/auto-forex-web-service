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

## Rate Limiting

The nginx configuration implements rate limiting to protect against abuse and DDoS attacks. When rate limits are exceeded, nginx returns HTTP status code **429 Too Many Requests**.

### Rate Limit Zones

Two rate limiting zones are configured in `nginx.conf`:

1. **api_limit**: General API endpoints

   - Rate: 100 requests per minute per IP address
   - Burst: 20 additional requests allowed
   - Applied to: `/api/*` endpoints

2. **login_limit**: Authentication and admin endpoints
   - Rate: 5 requests per minute per IP address
   - Burst: 3-5 additional requests allowed
   - Applied to: `/api/auth/login` and `/api/admin/*` endpoints

### Configuration Details

```nginx
# In nginx.conf
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/m;
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;
limit_req_status 429;  # Return 429 Too Many Requests on limit exceeded
```

### Endpoint-Specific Limits

| Endpoint Pattern  | Rate Limit  | Burst | Status Code |
| ----------------- | ----------- | ----- | ----------- |
| `/api/*`          | 100 req/min | 20    | 429         |
| `/api/admin/*`    | 5 req/min   | 5     | 429         |
| `/api/auth/login` | 5 req/min   | 3     | 429         |

### How It Works

- **Rate**: The sustained request rate allowed per IP address
- **Burst**: Additional requests allowed in a short burst before rate limiting kicks in
- **nodelay**: Requests exceeding the burst are immediately rejected with 429 status
- **Zone Memory**: 10MB allocated per zone (sufficient for ~160,000 IP addresses)

### Testing Rate Limits

You can test rate limiting using curl or any HTTP client:

```bash
# Test API rate limit (100 req/min)
for i in {1..125}; do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost/api/accounts/
done

# Expected: First 120 requests return 200, remaining return 429
```

### Monitoring Rate Limits

Rate limit events are logged in nginx access logs:

```
/var/log/nginx/access.log
```

Look for entries with status code 429 to identify rate-limited requests.

## Switching Between Environments

The docker-compose files automatically use the correct configuration:

- `docker-compose.yaml` → Development (Dockerfile.dev)
- `docker-compose.prod.yaml` → Production (Dockerfile.prod)

No manual configuration changes needed!
