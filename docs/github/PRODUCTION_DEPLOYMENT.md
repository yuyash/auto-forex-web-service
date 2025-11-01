# Production Deployment Guide

## Overview

The CI/CD pipeline uses a production-specific docker-compose configuration that pulls pre-built images from DockerHub instead of building them locally.

## Files

### docker-compose.yaml (Development)

- Used for local development
- Builds images from source using `build:` directives
- Mounts source code as volumes for hot-reloading

### docker-compose.prod.yaml (Production)

- Used for production deployments via CI/CD
- Pulls pre-built images from DockerHub
- Uses `image:` directives with `${DOCKERHUB_USERNAME}/` prefix
- No source code volumes (code is baked into images)

## How It Works

### 1. Build Phase (GitHub Actions)

When code is pushed to GitHub:

1. Three Docker images are built in parallel for multiple architectures:
   - `${DOCKERHUB_USERNAME}/forex-trading-backend:latest`
   - `${DOCKERHUB_USERNAME}/forex-trading-frontend:latest`
   - `${DOCKERHUB_USERNAME}/forex-trading-nginx:latest`
2. Images are built for both:
   - **linux/amd64** (x86_64) - Intel/AMD processors
   - **linux/arm64** (aarch64) - ARM processors (Raspberry Pi, Apple Silicon, AWS Graviton)
3. Images are tagged with:
   - Branch name (e.g., `main`, `develop`)
   - Commit SHA (e.g., `main-abc1234`)
   - `latest` (only for main branch)
4. Multi-architecture manifest is pushed to DockerHub

### 2. Deploy Phase (GitHub Actions)

When deploying to production:

1. `docker-compose.prod.yaml` is copied to server as `docker-compose.yaml`
2. `DOCKERHUB_USERNAME` is added to server's `.env` file
3. `docker compose pull` downloads latest images from DockerHub
4. `docker compose up -d` starts containers with new images

## Required Environment Variables

### On Server (.env file)

```env
# DockerHub Configuration (REQUIRED)
DOCKERHUB_USERNAME=your-dockerhub-username

# Database
DB_NAME=forex_trading
DB_USER=postgres
DB_PASSWORD=your-secure-password

# Django
SECRET_KEY=your-django-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com

# Redis (optional - leave empty for no authentication)
# Note: If empty, Redis will run without password authentication
# Recommended: Set a strong password for production environments
REDIS_PASSWORD=your-redis-password

# Security
ENCRYPTION_KEY=your-encryption-key

# OANDA API
OANDA_PRACTICE_API=https://api-fxpractice.oanda.com
OANDA_LIVE_API=https://api-fxtrade.oanda.com
```

**Important Notes:**

- `REDIS_PASSWORD` is optional. If left empty or unset, Redis will run without authentication
- For production, it's recommended to set a strong Redis password
- The Redis configuration automatically adapts based on whether a password is provided

### In GitHub Secrets

- `DOCKERHUB_USERNAME` - Your DockerHub username
- `DOCKERHUB_TOKEN` - DockerHub access token
- `SSH_PRIVATE_KEY` - SSH private key for server access
- `SERVER_HOST` - Production server hostname/IP
- `SERVER_USER` - SSH username
- `DEPLOY_PATH` - Deployment directory path
- `SSH_PORT` (optional) - SSH port (default: 22)

## Image Naming Convention

All images follow this pattern:

```
${DOCKERHUB_USERNAME}/forex-trading-{service}:{tag}
```

Examples:

- `myusername/forex-trading-backend:latest`
- `myusername/forex-trading-backend:main`
- `myusername/forex-trading-backend:main-abc1234`
- `myusername/forex-trading-frontend:latest`
- `myusername/forex-trading-nginx:latest`

## Manual Deployment

If you need to deploy manually:

```bash
# 1. Set environment variables
export SERVER_HOST=your-server
export SERVER_USER=your-user
export DEPLOY_PATH=/path/to/deploy
export SSH_PORT=22  # optional

# 2. Copy production docker-compose
scp -P ${SSH_PORT} docker-compose.prod.yaml ${SERVER_USER}@${SERVER_HOST}:${DEPLOY_PATH}/docker-compose.yaml

# 3. SSH into server
ssh -p ${SSH_PORT} ${SERVER_USER}@${SERVER_HOST}

# 4. Navigate to deployment directory
cd ${DEPLOY_PATH}

# 5. Ensure DOCKERHUB_USERNAME is in .env
echo "DOCKERHUB_USERNAME=your-username" >> .env

# 6. Pull latest images
docker compose pull

# 7. Restart services
docker compose down
docker compose up -d

# 8. Verify deployment
docker compose ps
docker compose logs -f
```

## Switching Between Development and Production

### Development (Local)

```bash
# Use development docker-compose
docker compose -f docker-compose.yaml up -d

# Or simply
docker compose up -d
```

### Production (Server)

```bash
# Use production docker-compose (copied from docker-compose.prod.yaml)
docker compose up -d
```

## Troubleshooting

### Images Not Pulling

**Problem**: `docker compose pull` fails

**Solutions**:

1. Verify `DOCKERHUB_USERNAME` is set in `.env`
2. Check images exist on DockerHub: `https://hub.docker.com/u/your-username`
3. Verify image names match: `docker compose config | grep image:`
4. Check DockerHub rate limits (pull limit for free accounts)

### Wrong Images Being Used

**Problem**: Old images are being used

**Solutions**:

1. Pull latest images: `docker compose pull`
2. Force recreate containers: `docker compose up -d --force-recreate`
3. Remove old images: `docker image prune -af`
4. Check image tags: `docker images | grep forex-trading`

### Build vs Pull Confusion

**Problem**: Server is trying to build instead of pull

**Solutions**:

1. Verify you're using `docker-compose.prod.yaml` (not `docker-compose.yaml`)
2. Check file was copied correctly: `cat docker-compose.yaml | grep "image:"`
3. Ensure no `build:` directives exist in production compose file

### Redis Configuration Issues

**Problem**: Redis fails to start with "wrong number of arguments" error

**Solutions**:

1. Check if `REDIS_PASSWORD` is properly set in `.env`
2. If you don't want authentication, ensure `REDIS_PASSWORD` is either:
   - Not set in `.env` at all, OR
   - Set to empty value: `REDIS_PASSWORD=`
3. Restart Redis: `docker compose restart redis`
4. Check Redis logs: `docker compose logs redis`

**Problem**: Cannot connect to Redis

**Solutions**:

1. If using password: Verify `REDIS_PASSWORD` matches in all services
2. Check Redis is running: `docker compose ps redis`
3. Test connection:

   ```bash
   # With password
   docker compose exec redis redis-cli -a "your-password" ping

   # Without password
   docker compose exec redis redis-cli ping
   ```

## Best Practices

1. **Always use docker-compose.prod.yaml for production**

   - Never use docker-compose.yaml on production servers
   - It will try to build from source (which won't exist)

2. **Tag images properly**

   - Use semantic versioning for releases
   - Keep `latest` tag for main branch
   - Use commit SHAs for traceability

3. **Test images before deploying**

   - Pull and test images locally before production deployment
   - Verify image sizes are reasonable
   - Check for security vulnerabilities

4. **Monitor DockerHub usage**

   - Free accounts have pull rate limits
   - Consider upgrading for production use
   - Use image caching strategies

5. **Keep .env secure**
   - Never commit .env to git
   - Use strong passwords
   - Rotate credentials regularly

## SSL/TLS Certificate Setup (One-Time)

Before your first production deployment, you need to set up SSL certificates for HTTPS.

### Prerequisites

- Domain name pointing to your server's IP address
- Ports 80 and 443 open in firewall
- Server accessible from the internet

### Let's Encrypt Setup (Recommended - Free)

1. **Verify DNS is configured**:

   ```bash
   nslookup your-domain.com
   # Should return your server's IP address
   ```

2. **SSH into your production server**:

   ```bash
   ssh -p ${SSH_PORT:-22} ${SERVER_USER}@${SERVER_HOST}
   cd ${DEPLOY_PATH}
   ```

3. **Create required directories**:

   ```bash
   mkdir -p certbot/conf certbot/www nginx/conf.d config logs
   ```

   **Important**: The `nginx/conf.d` directory will be mounted into the nginx container to provide custom configuration.

4. **Create initial HTTP-only nginx config**:

   ```bash
   cat > nginx/conf.d/default.conf << 'EOF'
   server {
   listen 80;
   server_name your-domain.com www.your-domain.com;

   location /.well-known/acme-challenge/ {
      root /var/www/certbot;
   }

   location / {
      return 301 https://$host$request_uri;
   }
   }
   EOF
   ```

5. **Start nginx temporarily for certificate generation**:

   ```bash
   docker compose up -d nginx
   ```

6. **Request SSL certificate from Let's Encrypt**:

   ```bash
   docker compose run --rm certbot certonly \
     --webroot \
     --webroot-path=/var/www/certbot \
     --email your-email@example.com \
     --agree-tos \
     --no-eff-email \
     -d your-domain.com \
     -d www.your-domain.com
   ```

7. **Update nginx config for HTTPS**:

   ```bash
   cat > nginx/conf.d/default.conf << 'EOF'
   # Redirect HTTP to HTTPS
   server {
       listen 80;
       server_name your-domain.com www.your-domain.com;

       location /.well-known/acme-challenge/ {
           root /var/www/certbot;
       }

       location / {
           return 301 https://$host$request_uri;
       }
   }

   # HTTPS server
   server {
       listen 443 ssl http2;
       server_name your-domain.com www.your-domain.com;

       # SSL certificates
       ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

       # SSL configuration
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_ciphers HIGH:!aNULL:!MD5;
       ssl_prefer_server_ciphers on;
       ssl_session_cache shared:SSL:10m;
       ssl_session_timeout 10m;

       # Security headers
       add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
       add_header X-Frame-Options "SAMEORIGIN" always;
       add_header X-Content-Type-Options "nosniff" always;
       add_header X-XSS-Protection "1; mode=block" always;

       # Rate limiting
       limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/m;

       # Frontend
       location / {
           proxy_pass http://frontend:80;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       # Backend API
       location /api/ {
           limit_req zone=api_limit burst=20 nodelay;
           proxy_pass http://backend:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_read_timeout 300s;
       }

       # WebSocket
       location /ws/ {
           proxy_pass http://backend:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_read_timeout 86400;
       }

       # Static files
       location /static/ {
           alias /app/staticfiles/;
           expires 30d;
           add_header Cache-Control "public, immutable";
       }

       # Media files
       location /media/ {
           alias /app/media/;
           expires 7d;
           add_header Cache-Control "public";
       }
   }
   EOF
   ```

8. **Reload nginx with new configuration**:

   ```bash
   docker compose restart nginx
   ```

9. **Verify SSL is working**:

   ```bash
   # Test HTTPS
   curl -I https://your-domain.com

   # Check certificate details
   echo | openssl s_client -connect your-domain.com:443 -servername your-domain.com 2>/dev/null | openssl x509 -noout -dates
   ```

10. **Test automatic renewal** (optional):
    ```bash
    docker compose run --rm certbot renew --dry-run
    ```

### Certificate Auto-Renewal

The certbot container automatically renews certificates every 12 hours. No manual intervention needed.

To manually renew:

```bash
docker compose run --rm certbot renew
docker compose restart nginx
```

### Using Custom SSL Certificates

If you have your own SSL certificate:

1. **Copy certificate files to server**:

   ```bash
   # Create directory structure
   mkdir -p certbot/conf/live/your-domain.com

   # Copy your certificate files
   scp your-fullchain.pem user@server:${DEPLOY_PATH}/certbot/conf/live/your-domain.com/fullchain.pem
   scp your-privkey.pem user@server:${DEPLOY_PATH}/certbot/conf/live/your-domain.com/privkey.pem
   ```

2. **Set proper permissions**:

   ```bash
   chmod 644 certbot/conf/live/your-domain.com/fullchain.pem
   chmod 600 certbot/conf/live/your-domain.com/privkey.pem
   ```

3. **Use the HTTPS nginx config from step 7 above**

4. **Restart nginx**:
   ```bash
   docker compose restart nginx
   ```

### Troubleshooting SSL Setup

**Problem**: Certificate generation fails with "Connection refused"

**Solutions**:

- Verify DNS: `dig your-domain.com` should show your server IP
- Check port 80 is open: `sudo ufw status` or `sudo iptables -L`
- Test port accessibility: `curl http://your-domain.com`
- Check nginx is running: `docker compose ps nginx`

**Problem**: "Too many certificates already issued"

**Solutions**:

- Let's Encrypt has rate limits (50 certs/week per domain)
- Use staging environment for testing: add `--staging` flag
- Wait for rate limit to reset (usually 7 days)
- Use different subdomains if needed

**Problem**: HTTPS not working after certificate generation

**Solutions**:

- Verify certificate files exist: `ls -la certbot/conf/live/your-domain.com/`
- Check nginx config syntax: `docker compose exec nginx nginx -t`
- View nginx logs: `docker compose logs nginx`
- Restart nginx: `docker compose restart nginx`
- Check firewall allows port 443: `sudo ufw allow 443/tcp`

**Problem**: Certificate renewal fails

**Solutions**:

- Check certbot logs: `docker compose logs certbot`
- Manually renew: `docker compose run --rm certbot renew --force-renewal`
- Verify webroot path is accessible
- Check nginx is serving /.well-known/acme-challenge/

### Security Best Practices

1. **Use strong SSL configuration**:

   - TLS 1.2 and 1.3 only
   - Strong cipher suites
   - HSTS enabled

2. **Monitor certificate expiration**:

   - Let's Encrypt certs expire after 90 days
   - Auto-renewal runs every 12 hours
   - Set up monitoring/alerts

3. **Test SSL configuration**:

   - Use SSL Labs: https://www.ssllabs.com/ssltest/
   - Should achieve A or A+ rating

4. **Keep nginx updated**:
   - Regularly update nginx image
   - Monitor security advisories

## Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [DockerHub Documentation](https://docs.docker.com/docker-hub/)
- [GitHub Actions Docker Build](https://docs.github.com/en/actions/publishing-packages/publishing-docker-images)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Certbot Documentation](https://certbot.eff.org/docs/)
- [Nginx SSL Configuration](https://nginx.org/en/docs/http/configuring_https_servers.html)
