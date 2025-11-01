.PHONY: help build up down restart logs shell migrate test clean backup

# Default target
help:
	@echo "Auto Forex Trading System - Docker Commands"
	@echo ""
	@echo "Available commands:"
	@echo "  make build          - Build all Docker images"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make logs           - View logs (all services)"
	@echo "  make logs-backend   - View backend logs"
	@echo "  make logs-celery    - View celery logs"
	@echo "  make shell          - Open Django shell"
	@echo "  make migrate        - Run database migrations"
	@echo "  make superuser      - Create Django superuser"
	@echo "  make test           - Run backend tests"
	@echo "  make test-frontend  - Run frontend tests"
	@echo "  make clean          - Remove containers and volumes"
	@echo "  make backup         - Backup database"
	@echo "  make restore        - Restore database from backup"
	@echo "  make ps             - Show service status"
	@echo "  make stats          - Show resource usage"

# Build Docker images
build:
	docker-compose build

# Start all services
up:
	docker-compose up -d
	@echo "Services started. Access at http://localhost"

# Stop all services
down:
	docker-compose down

# Restart all services
restart:
	docker-compose restart

# View logs
logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-celery:
	docker-compose logs -f celery

logs-nginx:
	docker-compose logs -f nginx

# Django shell
shell:
	docker-compose exec backend python manage.py shell

# Database migrations
migrate:
	docker-compose exec backend python manage.py migrate

# Create superuser
superuser:
	docker-compose exec backend python manage.py createsuperuser

# Run tests
test:
	docker-compose exec backend pytest

test-frontend:
	docker-compose exec frontend npm test

# Clean up
clean:
	docker-compose down -v
	@echo "All containers and volumes removed"

# Database backup
backup:
	@mkdir -p backups
	@echo "Creating database backup..."
	docker-compose exec -T postgres pg_dump -U postgres forex_trading | gzip > backups/backup_$$(date +%Y%m%d_%H%M%S).sql.gz
	@echo "Backup created in backups/"

# Database restore
restore:
	@echo "Available backups:"
	@ls -lh backups/*.sql.gz
	@echo ""
	@read -p "Enter backup filename: " backup; \
	gunzip -c backups/$$backup | docker-compose exec -T postgres psql -U postgres forex_trading

# Show service status
ps:
	docker-compose ps

# Show resource usage
stats:
	docker stats --no-stream

# Development setup
dev-setup:
	@echo "Setting up development environment..."
	cp .env.example .env
	@echo "Please edit .env file with your configuration"
	@echo "Then run: make build && make up && make migrate && make superuser"

# Production setup
prod-setup:
	@echo "Setting up production environment..."
	@echo "1. Configure .env file"
	@echo "2. Run: make ssl-init"
	@echo "3. Run: make build && make up"
	@echo "4. Run: make migrate && make superuser"

# Quick development start
dev:
	make build
	make up
	sleep 5
	make migrate
	@echo ""
	@echo "Development environment ready!"
	@echo "Create superuser with: make superuser"
	@echo "Access at: http://localhost"

# Health check
health:
	@echo "Checking service health..."
	@docker-compose ps
	@echo ""
	@echo "Backend health:"
	@curl -s http://localhost/api/health || echo "Backend not responding"
	@echo ""
	@echo "Database connection:"
	@docker-compose exec backend python manage.py dbshell -c "SELECT 1;" || echo "Database not accessible"
