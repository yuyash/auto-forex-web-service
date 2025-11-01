# GitHub Actions CI/CD Quick Reference

## Quick Commands

### Validate Workflow

```bash
./.github/scripts/validate-workflow.sh
```

### Test SSH Connection

```bash
export SERVER_HOST=your-server
export SERVER_USER=your-user
export DEPLOY_PATH=/path/to/deploy
./.github/scripts/deploy.sh test-ssh
```

### Manual Deployment

```bash
export SERVER_HOST=your-server
export SERVER_USER=your-user
export DEPLOY_PATH=/path/to/deploy
./.github/scripts/deploy.sh deploy
```

### Verify Deployment

```bash
export SERVER_HOST=your-server
export SERVER_USER=your-user
export DEPLOY_PATH=/path/to/deploy
./.github/scripts/deploy.sh verify
```

### Rollback

```bash
export SERVER_HOST=your-server
export SERVER_USER=your-user
export DEPLOY_PATH=/path/to/deploy
./.github/scripts/deploy.sh rollback
```

## Required GitHub Secrets

| Secret               | Description                       |
| -------------------- | --------------------------------- |
| `DOCKERHUB_USERNAME` | DockerHub username                |
| `DOCKERHUB_TOKEN`    | DockerHub access token            |
| `SSH_PRIVATE_KEY`    | SSH private key for server access |
| `SERVER_HOST`        | Production server hostname/IP     |
| `SERVER_USER`        | SSH username                      |
| `DEPLOY_PATH`        | Deployment directory path         |

## Workflow Triggers

| Event             | Action                   |
| ----------------- | ------------------------ |
| Push to `main`    | Build + Deploy           |
| Push to `develop` | Build only               |
| Pull Request      | Build + Validate         |
| Manual trigger    | Build + Deploy (if main) |

## Docker Image Tags

| Tag Type | Example           | When Applied     |
| -------- | ----------------- | ---------------- |
| Branch   | `main`, `develop` | All pushes       |
| SHA      | `main-abc1234`    | All pushes       |
| Latest   | `latest`          | Main branch only |
| PR       | `pr-123`          | Pull requests    |

## Common Issues & Solutions

### Build Fails

```bash
# Check workflow logs in GitHub Actions tab
# Verify Dockerfile syntax
# Check dependencies are available
```

### Deployment Fails

```bash
# Test SSH connection
ssh -i ~/.ssh/key user@server

# Check Docker on server
ssh user@server "docker ps"

# View server logs
ssh user@server "cd /deploy/path && docker compose logs"
```

### Images Not Pushing

```bash
# Verify DockerHub credentials
# Check token permissions (Read, Write, Delete)
# Verify repository names match
```

## Server Commands

### Check Container Status

```bash
ssh user@server "cd /deploy/path && docker compose ps"
```

### View Logs

```bash
ssh user@server "cd /deploy/path && docker compose logs -f"
```

### Restart Services

```bash
ssh user@server "cd /deploy/path && docker compose restart"
```

### Pull Latest Images

```bash
ssh user@server "cd /deploy/path && docker compose pull"
```

### Clean Up

```bash
ssh user@server "docker system prune -af"
```

## Monitoring

### GitHub Actions

- Go to repository → Actions tab
- View workflow runs and logs
- Check build times and success rates

### DockerHub

- Check image sizes and tags
- Monitor pull statistics
- Verify image updates

### Production Server

```bash
# Check disk space
ssh user@server "df -h"

# Check memory usage
ssh user@server "free -h"

# Check Docker stats
ssh user@server "docker stats --no-stream"
```

## Emergency Procedures

### Stop All Services

```bash
ssh user@server "cd /deploy/path && docker compose down"
```

### Quick Rollback

```bash
ssh user@server "cd /deploy/path && docker compose down && docker compose up -d"
```

### View Recent Logs

```bash
ssh user@server "cd /deploy/path && docker compose logs --tail=100"
```

## Documentation Links

- **Setup Guide**: `.github/SETUP_GUIDE.md`
- **Full Documentation**: `.github/README.md`
- **Implementation Details**: `.github/IMPLEMENTATION_SUMMARY.md`
- **Secrets Template**: `.github/secrets.template.env`

## Support Checklist

Before asking for help:

- [ ] Checked workflow logs in GitHub Actions
- [ ] Verified all secrets are configured
- [ ] Tested SSH connection manually
- [ ] Checked server logs
- [ ] Verified Docker is running on server
- [ ] Checked disk space on server
- [ ] Reviewed error messages carefully

## Useful Links

- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [Docker Docs](https://docs.docker.com/)
- [Docker Compose Docs](https://docs.docker.com/compose/)
- [DockerHub](https://hub.docker.com/)
