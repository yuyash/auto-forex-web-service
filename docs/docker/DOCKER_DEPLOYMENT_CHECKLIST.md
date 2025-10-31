# Docker Deployment Checklist

Use this checklist to ensure a successful deployment of the Auto Forex Trading System.

## Pre-Deployment Checklist

### System Requirements

- [ ] Docker Engine 20.10+ installed
- [ ] Docker Compose 2.0+ installed
- [ ] Minimum 4GB RAM available
- [ ] Minimum 20GB disk space available
- [ ] Ports 80 and 443 available and not in use

### Network Requirements (Production)

- [ ] Domain name registered
- [ ] DNS A record pointing to server IP
- [ ] Router port forwarding configured (80, 443)
- [ ] DDNS configured (if using dynamic IP)
- [ ] Firewall allows ports 80 and 443

### Files Verification

- [ ] `docker-compose.yaml` exists
- [ ] `backend/Dockerfile` exists
- [ ] `frontend/Dockerfile` exists
- [ ] `nginx/Dockerfile` exists
- [ ] `nginx/nginx.conf` exists
- [ ] `nginx/conf.d/default.conf` exists
- [ ] `.env.example` exists
- [ ] `init-letsencrypt.sh` is executable

## Configuration Checklist

### Environment Variables

- [ ] Copy `.env.example` to `.env`
- [ ] Set `DB_PASSWORD` (strong password)
- [ ] Set `REDIS_PASSWORD` (strong password)
- [ ] Set `SECRET_KEY` (50+ characters)
- [ ] Set `ENCRYPTION_KEY` (Fernet key)
- [ ] Set `ALLOWED_HOSTS` (your domain)
- [ ] Set `DEBUG=False` (production)
- [ ] Configure OANDA API endpoints (if different)
- [ ] Configure AWS credentials (for backtesting)

### Generate Required Keys

```bash
# Encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Django secret key
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Nginx Configuration (Production)

- [ ] Update `nginx/conf.d/default.conf` with your domain
- [ ] Replace `your-domain.com` with actual domain
- [ ] Verify SSL certificate paths match domain

## Development Deployment

### Quick Start

```bash
# 1. Setup environment
make dev-setup

# 2. Edit .env file
nano .env

# 3. Start services
make dev

# 4. Create superuser
make superuser
```

### Verification

- [ ] All services running: `make ps`
- [ ] Backend accessible: http://localhost/api/
- [ ] Frontend accessible: http://localhost
- [ ] Database migrations applied
- [ ] Superuser created
- [ ] Can login to admin panel

## Production Deployment

### Initial Setup

```bash
# 1. Configure environment
cp .env.example .env
nano .env

# 2. Set domain and email
export DOMAIN=yourdomain.com
export EMAIL=your-email@example.com

# 3. Initialize SSL certificates
./init-letsencrypt.sh

# 4. Build and start services
make build
make up

# 5. Initialize database
make migrate
make superuser
```

### SSL Certificate Setup

- [ ] Domain DNS configured and propagated
- [ ] Port 80 accessible from internet
- [ ] `init-letsencrypt.sh` executed successfully
- [ ] SSL certificates created in `certbot/conf/live/`
- [ ] Nginx reloaded with new certificates
- [ ] HTTPS accessible: https://yourdomain.com
- [ ] HTTP redirects to HTTPS

### Service Verification

- [ ] All services healthy: `docker-compose ps`
- [ ] No errors in logs: `make logs`
- [ ] Backend health check: `curl https://yourdomain.com/api/health`
- [ ] Frontend loads correctly
- [ ] WebSocket connections work
- [ ] Admin panel accessible
- [ ] Can create user accounts
- [ ] Can login successfully

## Security Checklist

### Application Security

- [ ] `DEBUG=False` in production
- [ ] Strong database password set
- [ ] Strong Redis password set
- [ ] Unique Django secret key
- [ ] Unique encryption key
- [ ] `ALLOWED_HOSTS` configured correctly
- [ ] CSRF protection enabled
- [ ] Rate limiting configured

### Network Security

- [ ] Firewall configured (only 80, 443 open)
- [ ] Database port (5432) not exposed to internet
- [ ] Redis port (6379) not exposed to internet
- [ ] SSH access secured (key-based auth)
- [ ] SSL/TLS certificates valid
- [ ] HSTS header enabled
- [ ] Security headers configured

### Data Security

- [ ] API tokens encrypted in database
- [ ] Passwords hashed with bcrypt
- [ ] Backup encryption configured (optional)
- [ ] Volume permissions correct
- [ ] Sensitive files not in git

## Post-Deployment Checklist

### Monitoring Setup

- [ ] Log rotation configured
- [ ] Health check monitoring enabled
- [ ] Disk space monitoring enabled
- [ ] Memory usage monitoring enabled
- [ ] CPU usage monitoring enabled
- [ ] Alert notifications configured

### Backup Configuration

- [ ] Database backup script created
- [ ] Backup schedule configured (cron)
- [ ] Backup retention policy set
- [ ] Backup restoration tested
- [ ] Volume backups configured
- [ ] Off-site backup configured (optional)

### Maintenance Tasks

- [ ] SSL certificate auto-renewal verified
- [ ] Log rotation working
- [ ] Backup script tested
- [ ] Update procedure documented
- [ ] Rollback procedure documented
- [ ] Emergency contacts documented

## Testing Checklist

### Functional Testing

- [ ] User registration works
- [ ] User login works
- [ ] User logout works
- [ ] Password reset works (if implemented)
- [ ] OANDA account can be added
- [ ] Strategy can be configured
- [ ] Strategy can be started
- [ ] Strategy can be stopped
- [ ] Real-time data updates work
- [ ] WebSocket connections stable
- [ ] Orders can be placed (test account)
- [ ] Positions tracked correctly
- [ ] Admin dashboard accessible
- [ ] Event logging working

### Performance Testing

- [ ] Page load times acceptable (< 3s)
- [ ] API response times acceptable (< 500ms)
- [ ] WebSocket latency acceptable (< 100ms)
- [ ] Database queries optimized
- [ ] Static files cached correctly
- [ ] Gzip compression working
- [ ] No memory leaks observed
- [ ] CPU usage reasonable under load

### Security Testing

- [ ] SQL injection attempts blocked
- [ ] XSS attempts blocked
- [ ] CSRF protection working
- [ ] Rate limiting working
- [ ] Unauthorized access blocked
- [ ] Admin endpoints protected
- [ ] JWT tokens expire correctly
- [ ] Session management secure

## Troubleshooting Checklist

### Services Won't Start

- [ ] Check logs: `make logs`
- [ ] Verify environment variables: `docker-compose config`
- [ ] Check port conflicts: `netstat -tulpn | grep -E '80|443|5432|6379'`
- [ ] Verify Docker daemon running: `systemctl status docker`
- [ ] Check disk space: `df -h`
- [ ] Check memory: `free -h`

### Database Issues

- [ ] PostgreSQL container running: `docker-compose ps postgres`
- [ ] Database accessible: `make shell` then try DB query
- [ ] Migrations applied: `make migrate`
- [ ] Check database logs: `docker-compose logs postgres`
- [ ] Verify credentials in .env

### SSL Certificate Issues

- [ ] Domain DNS resolves correctly: `nslookup yourdomain.com`
- [ ] Port 80 accessible: `curl http://yourdomain.com/.well-known/acme-challenge/`
- [ ] Certificate files exist: `ls -la certbot/conf/live/yourdomain.com/`
- [ ] Nginx configuration valid: `docker-compose exec nginx nginx -t`
- [ ] Check certbot logs: `docker-compose logs certbot`

### Performance Issues

- [ ] Check resource usage: `docker stats`
- [ ] Check database connections: `docker-compose exec postgres psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"`
- [ ] Check Redis memory: `docker-compose exec redis redis-cli INFO memory`
- [ ] Check Celery queue: `docker-compose exec celery celery -A trading_system inspect active`
- [ ] Review slow query logs
- [ ] Check for memory leaks

## Maintenance Schedule

### Daily

- [ ] Check service health: `make ps`
- [ ] Review error logs: `make logs | grep ERROR`
- [ ] Monitor disk space: `df -h`
- [ ] Check backup completion

### Weekly

- [ ] Review all logs for issues
- [ ] Check SSL certificate expiry
- [ ] Verify backup restoration
- [ ] Review security logs
- [ ] Check for application updates

### Monthly

- [ ] Update dependencies (security patches)
- [ ] Review and optimize database
- [ ] Clean up old logs
- [ ] Review backup retention
- [ ] Performance audit
- [ ] Security audit

### Quarterly

- [ ] Full system backup
- [ ] Disaster recovery test
- [ ] Security penetration test
- [ ] Performance load test
- [ ] Documentation review
- [ ] Update runbooks

## Emergency Procedures

### Service Down

1. Check service status: `make ps`
2. Review logs: `make logs`
3. Restart service: `docker-compose restart <service>`
4. If persistent, rebuild: `make build && make up`

### Database Corruption

1. Stop all services: `make down`
2. Restore from backup: `make restore`
3. Verify data integrity
4. Restart services: `make up`
5. Run migrations: `make migrate`

### Security Breach

1. Immediately stop all services: `make down`
2. Rotate all credentials
3. Review logs for unauthorized access
4. Restore from clean backup
5. Apply security patches
6. Restart with new credentials

### SSL Certificate Expired

1. Renew certificate: `make ssl-renew`
2. Reload nginx: `docker-compose exec nginx nginx -s reload`
3. Verify HTTPS working
4. Check auto-renewal: `docker-compose logs certbot`

## Sign-Off

### Development Deployment

- [ ] All development checklist items completed
- [ ] Tested by: ********\_******** Date: ****\_****
- [ ] Approved by: ******\_\_\_****** Date: ****\_****

### Production Deployment

- [ ] All production checklist items completed
- [ ] All security items verified
- [ ] All monitoring configured
- [ ] All backups tested
- [ ] Deployed by: ******\_\_\_****** Date: ****\_****
- [ ] Verified by: ******\_\_\_****** Date: ****\_****
- [ ] Approved by: ******\_\_\_****** Date: ****\_****

## Notes

Document any deviations from standard deployment or special configurations:

```
_________________________________________________________________

_________________________________________________________________

_________________________________________________________________

_________________________________________________________________
```

## Support Contacts

- System Administrator: ****************\_\_\_****************
- Database Administrator: ****************\_****************
- Security Team: ********************\_\_********************
- On-Call Support: ******************\_\_\_\_******************
- Emergency Contact: ******************\_\_******************

---

**Last Updated**: [Date]
**Version**: 1.0
**Next Review**: [Date]
