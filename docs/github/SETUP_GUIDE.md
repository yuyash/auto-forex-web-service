# GitHub Actions CI/CD Setup Guide

This guide will walk you through setting up the automated CI/CD pipeline for the Auto Forex Trading System.

## Prerequisites

Before you begin, ensure you have:

- [ ] A GitHub repository for this project
- [ ] A DockerHub account
- [ ] A production server with Docker and Docker Compose installed
- [ ] SSH access to the production server
- [ ] Admin access to the GitHub repository (to configure secrets)

## Step 1: Prepare Your DockerHub Account

1. **Create a DockerHub account** (if you don't have one):

   - Go to https://hub.docker.com/signup
   - Complete the registration

2. **Create an access token**:

   - Log in to DockerHub
   - Go to Account Settings → Security → New Access Token
   - Name: `github-actions-forex-trading`
   - Permissions: Read, Write, Delete
   - Click "Generate" and **copy the token** (you won't see it again!)

3. **Create repositories** (optional - they'll be created automatically on first push):
   - `your-username/forex-trading-backend`
   - `your-username/forex-trading-frontend`
   - `your-username/forex-trading-nginx`

## Step 2: Prepare Your Production Server

1. **Install Docker and Docker Compose**:

   ```bash
   # Update package list
   sudo apt update

   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh

   # Add your user to docker group
   sudo usermod -aG docker $USER

   # Log out and back in for group changes to take effect
   ```

2. **Create deployment directory**:

   ```bash
   mkdir -p ~/forex-trading-system
   cd ~/forex-trading-system
   ```

3. **Verify Docker installation**:
   ```bash
   docker --version
   docker compose version
   docker ps
   ```

## Step 3: Set Up SSH Access

1. **Generate SSH key pair** (on your local machine):

   ```bash
   ssh-keygen -t ed25519 -C "git@github.com:forex-trading-deploy" -f ~/.ssh/github-actions-forex
   ```

2. **Copy public key to server**:

   ```bash
   ssh-copy-id -i ~/.ssh/github-actions-forex.pub user@your-server-host
   ```

3. **Test SSH connection**:

   ```bash
   ssh -i ~/.ssh/github-actions-forex user@your-server-host
   ```

4. **Get the private key content**:
   ```bash
   cat ~/.ssh/github-actions-forex
   ```
   Copy the entire output including the `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----` lines.

## Step 4: Configure GitHub Secrets

1. **Go to your GitHub repository**
2. **Navigate to Settings → Secrets and variables → Actions**
3. **Click "New repository secret"**
4. **Add each of the following secrets**:

### Required Secrets

| Secret Name           | Description                        | Example Value                              |
| --------------------- | ---------------------------------- | ------------------------------------------ |
| `DOCKERHUB_USERNAME`  | Your DockerHub username            | `myusername`                               |
| `DOCKERHUB_TOKEN`     | DockerHub access token from Step 1 | `dckr_pat_abc123...`                       |
| `SSH_PRIVATE_KEY`     | Private SSH key from Step 3        | `-----BEGIN OPENSSH PRIVATE KEY-----\n...` |
| `SERVER_HOST`         | Production server hostname or IP   | `trading.example.com` or `192.168.1.100`   |
| `SERVER_USER`         | SSH username on the server         | `ubuntu` or `deploy`                       |
| `DEPLOY_PATH`         | Deployment directory path          | `/home/ubuntu/forex-trading-system`        |
| `SSH_PORT` (optional) | SSH port number (default: 22)      | `22` or `2222`                             |

### Adding a Secret

For each secret:

1. Click "New repository secret"
2. Enter the **Name** (e.g., `DOCKERHUB_USERNAME`)
3. Enter the **Value**
4. Click "Add secret"

**Important Notes:**

- For `SSH_PRIVATE_KEY`, paste the entire private key including header and footer
- For `DEPLOY_PATH`, use the absolute path (e.g., `/home/ubuntu/forex-trading-system`)
- Double-check all values before saving - you can't view them again!

## Step 5: Prepare Environment Variables

1. **Create .env file on the server**:

   ```bash
   ssh user@your-server-host
   cd ~/forex-trading-system
   nano .env
   ```

2. **Add required environment variables**:

   ```env
   # Database Configuration
   DB_NAME=forex_trading
   DB_USER=postgres
   DB_PASSWORD=your-secure-password-here

   # Django Configuration
   SECRET_KEY=your-django-secret-key-min-50-chars
   DEBUG=False
   ALLOWED_HOSTS=your-domain.com,www.your-domain.com

   # Redis Configuration (optional password)
   REDIS_PASSWORD=your-redis-password-here

   # Security Configuration
   ENCRYPTION_KEY=your-encryption-key-32-chars-minimum

   # OANDA API Configuration (optional for initial setup)
   OANDA_PRACTICE_API=https://api-fxpractice.oanda.com
   OANDA_LIVE_API=https://api-fxtrade.oanda.com

   # Docker Configuration (required for production)
   DOCKERHUB_USERNAME=your-dockerhub-username

   # SSL/Domain Configuration (required for HTTPS)
   DOMAIN=your-domain.com
   EMAIL=your-email@example.com
   ```

   **📖 For complete environment variable reference, see [docs/ENVIRONMENT_VARIABLES.md](../ENVIRONMENT_VARIABLES.md)**

3. **Save and exit** (Ctrl+X, then Y, then Enter)

## Step 6: Validate Your Setup

1. **Run the validation script** (on your local machine):

   ```bash
   ./.github/scripts/validate-workflow.sh
   ```

2. **Check for any warnings or errors**

3. **Test SSH connection**:
   ```bash
   export SERVER_HOST=your-server-host
   export SERVER_USER=your-ssh-user
   export DEPLOY_PATH=/path/to/deployment
   ./.github/scripts/deploy.sh test-ssh
   ```

## Step 7: Test the Workflow

1. **Create a test branch**:

   ```bash
   git checkout -b test-ci-cd
   ```

2. **Make a small change** (e.g., update README.md)

3. **Commit and push**:

   ```bash
   git add .
   git commit -m "Test CI/CD pipeline"
   git push origin test-ci-cd
   ```

4. **Monitor the workflow**:

   - Go to your GitHub repository
   - Click on the "Actions" tab
   - You should see the "Build and Deploy" workflow running
   - Click on it to see detailed logs

5. **Verify the build**:
   - All three Docker images should build successfully
   - Images should be pushed to DockerHub
   - Deployment should be skipped (not on main branch)

## Step 8: Set Up SSL Certificates (One-Time Setup)

Before your first production deployment, you need to set up SSL certificates for HTTPS.

**📖 For complete SSL setup instructions, see [.github/PRODUCTION_DEPLOYMENT.md - SSL/TLS Certificate Setup](./PRODUCTION_DEPLOYMENT.md#ssltls-certificate-setup-one-time)**

### Quick SSL Setup (Let's Encrypt)

1. **Verify DNS is configured**:

   ```bash
   nslookup your-domain.com
   # Should return your server's IP address
   ```

2. **SSH into server**:

   ```bash
   ssh user@your-server-host
   cd ~/forex-trading-system
   ```

3. **Create required directories**:

   ```bash
   mkdir -p certbot/conf certbot/www nginx/conf.d config logs
   ```

   **Note**: The `nginx/conf.d` directory will contain your nginx configuration files that will be mounted into the nginx container.

4. **Stop all Docker services** (certbot standalone needs port 80):

   ```bash
   docker compose down
   ```

5. **Request certificate using standalone mode**:

   ```bash
   docker run --rm -it --network host \
   -v $(pwd)/certbot/conf:/etc/letsencrypt \
   -v $(pwd)/certbot/www:/var/www/certbot \
   certbot/certbot certonly \
   --standalone \
   --email yuya.shinde@gmail.com \
   --agree-tos \
   --no-eff-email \
   -d www.auto-forex.com
   ```

   **Note**: Uses `--network host` for direct port 80 access. Only include domains that point to your server.

6. **Configure nginx for HTTPS** (see full config in PRODUCTION_DEPLOYMENT.md)

7. **Start nginx**:

   ```bash
   docker compose restart nginx
   ```

8. **Verify HTTPS**:
   ```bash
   curl -I https://your-domain.com
   ```

### Important Notes

- DNS must be configured before requesting certificates
- Ports 80 and 443 must be open in firewall
- Certificates auto-renew every 12 hours
- See PRODUCTION_DEPLOYMENT.md for full nginx configuration and troubleshooting

## Step 9: Deploy to Production

1. **Merge to main branch**:

   ```bash
   git checkout main
   git merge test-ci-cd
   git push origin main
   ```

2. **Monitor deployment**:

   - Go to Actions tab in GitHub
   - Watch the deployment process
   - Verify all steps complete successfully

3. **Verify on server**:
   ```bash
   ssh user@your-server-host
   cd ~/forex-trading-system
   docker compose ps
   docker compose logs -f
   ```

## Troubleshooting

### Build Failures

**Problem**: Docker build fails

- Check Dockerfile syntax
- Verify all dependencies are available
- Check build logs in GitHub Actions

**Problem**: DockerHub push fails

- Verify DOCKERHUB_USERNAME and DOCKERHUB_TOKEN are correct
- Check token has write permissions
- Ensure repository names match

### Deployment Failures

**Problem**: SSH connection fails

- Verify SSH_PRIVATE_KEY is correct (including headers)
- Check SERVER_HOST and SERVER_USER are correct
- Test SSH manually: `ssh user@server-host`
- Verify SSH key is in server's authorized_keys

**Problem**: Docker commands fail on server

- Verify user is in docker group: `groups $USER`
- Check Docker is running: `sudo systemctl status docker`
- Verify Docker Compose is installed: `docker compose version`

**Problem**: Containers fail to start

- Check .env file on server has all required variables
- Verify docker-compose.yaml is valid: `docker compose config`
- Check container logs: `docker compose logs`
- Verify ports are not already in use: `sudo netstat -tulpn`

### Common Issues

**Issue**: "required variable is missing a value"

- **Solution**: Ensure .env file exists on server with all required variables

**Issue**: "Permission denied (publickey)"

- **Solution**: Verify SSH key is correctly added to GitHub secrets and server

**Issue**: "Cannot connect to Docker daemon"

- **Solution**: Add user to docker group and restart session

**Issue**: "Port already in use"

- **Solution**: Stop conflicting services or change ports in docker-compose.yaml

## Manual Deployment

If you need to deploy manually without GitHub Actions:

```bash
# Set environment variables
export SERVER_HOST=your-server-host
export SERVER_USER=your-ssh-user
export DEPLOY_PATH=/path/to/deployment

# Run deployment script
./.github/scripts/deploy.sh deploy
```

## Rollback

If a deployment causes issues:

```bash
# SSH into server
ssh user@server-host
cd /path/to/deployment

# View available image tags
docker images | grep forex-trading

# Update docker-compose.yaml to use previous tag
# Then restart services
docker compose down
docker compose up -d
```

## Next Steps

After successful deployment:

1. **Set up monitoring**: Configure health checks and alerts
2. **Configure SSL**: Set up Let's Encrypt certificates
3. **Set up backups**: Implement database backup strategy
4. **Configure logging**: Set up centralized logging
5. **Test the application**: Verify all features work in production

## Security Checklist

- [ ] All secrets are configured in GitHub (not in code)
- [ ] SSH key is unique to GitHub Actions (not reused)
- [ ] DockerHub token has minimal required permissions
- [ ] Server firewall is configured (only necessary ports open)
- [ ] .env file on server has secure passwords
- [ ] DJANGO_DEBUG is set to False in production
- [ ] DJANGO_ALLOWED_HOSTS is properly configured
- [ ] SSL/TLS is enabled (HTTPS only)
- [ ] Regular security updates are scheduled

## Support

If you encounter issues:

1. Check the [GitHub Actions documentation](https://docs.github.com/en/actions)
2. Review workflow logs in the Actions tab
3. Check server logs: `docker compose logs`
4. Consult the main README.md and DEPLOYMENT.md

## Production Deployment Notes

### Docker Compose Files

- **docker-compose.yaml**: For local development (builds from source)
- **docker-compose.prod.yaml**: For production (pulls pre-built images from DockerHub)

### Multi-Architecture Support

Images are built for both:

- **linux/amd64** (x86_64) - Intel/AMD processors
- **linux/arm64** (aarch64) - ARM processors (Raspberry Pi, Apple Silicon, AWS Graviton)

### Manual Production Deployment

```bash
# Copy production compose file
scp docker-compose.prod.yaml user@server:/path/to/deploy/docker-compose.yaml

# SSH into server
ssh user@server
cd /path/to/deploy

# Ensure DOCKERHUB_USERNAME is in .env
echo "DOCKERHUB_USERNAME=your-username" >> .env

# Pull and start services
docker compose pull
docker compose up -d
```

### Troubleshooting Production

**Images not pulling**: Verify `DOCKERHUB_USERNAME` in `.env` and check DockerHub

**Redis issues**: Ensure `REDIS_PASSWORD` is set correctly (or empty for no auth)

**SSL renewal fails**: Check certbot logs with `docker compose logs certbot`

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [DockerHub Documentation](https://docs.docker.com/docker-hub/)
- [SSH Key Management](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Certbot Documentation](https://certbot.eff.org/docs/)
