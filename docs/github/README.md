# GitHub Actions CI/CD Setup

This directory contains the GitHub Actions workflows for automated building and deployment of the Auto Forex Trader.

## Workflow Overview

The `build-and-deploy.yml` workflow performs the following tasks:

1. **Build Backend Docker Image**: Builds the Django backend application and pushes to DockerHub
2. **Build Frontend Docker Image**: Builds the React frontend application and pushes to DockerHub
3. **Build Nginx Docker Image**: Builds the Nginx reverse proxy and pushes to DockerHub
4. **Validate Docker Compose**: Validates the docker-compose.yaml configuration
5. **Deploy to Production**: Deploys the application to the production server via SSH (only on main branch)

## Triggers

The workflow is triggered on:

- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

Deployment to production only occurs on push to the `main` branch.

## Required GitHub Secrets

You must configure the following secrets in your GitHub repository settings (Settings → Secrets and variables → Actions):

### DockerHub Credentials

- **DOCKERHUB_USERNAME**: Your DockerHub username
- **DOCKERHUB_TOKEN**: Your DockerHub access token (create at https://hub.docker.com/settings/security)

### SSH Deployment Credentials

- **SSH_PRIVATE_KEY**: Private SSH key for accessing the production server

  - Generate with: `ssh-keygen -t ed25519 -C "github-actions@forex-trading"`
  - Add the public key to the server's `~/.ssh/authorized_keys`
  - Copy the private key content to this secret

- **SERVER_HOST**: Production server hostname or IP address

  - Example: `trading.example.com` or `192.168.1.100`

- **SERVER_USER**: SSH username for the production server

  - Example: `ubuntu` or `deploy`

- **DEPLOY_PATH**: Absolute path on the server where the application is deployed
  - Example: `/home/ubuntu/forex-trading-system`

## Setting Up Secrets

### 1. DockerHub Setup

```bash
# Login to DockerHub
docker login

# Create an access token at https://hub.docker.com/settings/security
# Add DOCKERHUB_USERNAME and DOCKERHUB_TOKEN to GitHub secrets
```

### 2. SSH Key Setup

```bash
# Generate SSH key pair
ssh-keygen -t ed25519 -C "github-actions@forex-trading" -f ~/.ssh/github-actions

# Copy public key to production server
ssh-copy-id -i ~/.ssh/github-actions.pub user@server-host

# Test SSH connection
ssh -i ~/.ssh/github-actions user@server-host

# Copy private key content to GitHub secret SSH_PRIVATE_KEY
cat ~/.ssh/github-actions
```

### 3. Server Preparation

On your production server, ensure:

1. Docker and Docker Compose are installed
2. The deployment directory exists: `mkdir -p /path/to/deploy`
3. The SSH public key is added to `~/.ssh/authorized_keys`
4. The user has permissions to run Docker commands (add to docker group):
   ```bash
   sudo usermod -aG docker $USER
   ```

## Docker Image Tagging Strategy

Images are tagged with:

- **Branch name**: `main`, `develop`
- **Commit SHA**: `main-abc1234`, `develop-xyz5678`
- **Latest**: Only for the main branch
- **PR number**: For pull requests

## Deployment Process

When code is pushed to the `main` branch:

1. All Docker images are built and pushed to DockerHub
2. Docker Compose configuration is validated
3. Images are pulled on the production server
4. Old containers are stopped and removed
5. New containers are started with the latest images
6. Old unused images are cleaned up
7. Deployment is verified by checking container status

## Manual Deployment

To manually trigger a deployment:

1. Go to Actions tab in GitHub
2. Select "Build and Deploy" workflow
3. Click "Run workflow"
4. Select the branch to deploy

## Troubleshooting

### Build Failures

- Check the build logs in the Actions tab
- Verify Dockerfile syntax and dependencies
- Ensure all required files are committed

### Deployment Failures

- Verify SSH credentials are correct
- Check server connectivity: `ssh user@server-host`
- Verify Docker is running on the server: `docker ps`
- Check server logs: `ssh user@server-host 'cd /deploy/path && docker compose logs'`

### DockerHub Push Failures

- Verify DOCKERHUB_USERNAME and DOCKERHUB_TOKEN are correct
- Check DockerHub access token has write permissions
- Ensure repository names match the configured image names

## Monitoring Deployments

After deployment, monitor the application:

```bash
# SSH into production server
ssh user@server-host

# Check running containers
cd /deploy/path
docker compose ps

# View logs
docker compose logs -f

# Check specific service logs
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f nginx
```

## Rollback Procedure

If a deployment fails or causes issues:

```bash
# SSH into production server
ssh user@server-host
cd /deploy/path

# Pull previous image version (replace with actual tag)
docker pull username/forex-trading-backend:previous-sha
docker pull username/forex-trading-frontend:previous-sha
docker pull username/forex-trading-nginx:previous-sha

# Update docker-compose.yaml to use specific tags
# Then restart services
docker compose down
docker compose up -d
```

## Security Best Practices

1. **Never commit secrets** to the repository
2. **Rotate SSH keys** regularly
3. **Use least privilege** for SSH user (only Docker permissions needed)
4. **Enable 2FA** on DockerHub account
5. **Restrict SSH access** to GitHub Actions IP ranges if possible
6. **Monitor deployment logs** for suspicious activity
7. **Keep secrets encrypted** in GitHub (they are by default)

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [SSH Agent Action](https://github.com/webfactory/ssh-agent)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
