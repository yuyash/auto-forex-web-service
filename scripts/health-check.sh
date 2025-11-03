#!/bin/bash
# Health check script for production services
# Usage: ./health-check.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yaml}"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_service() {
    local service=$1
    local status=$(docker compose -f "$COMPOSE_FILE" ps "$service" --format json 2>/dev/null | grep -o '"State":"[^"]*"' | cut -d'"' -f4)

    if [ "$status" = "running" ]; then
        echo -e "${GREEN}✓${NC} $service: Running"
        return 0
    else
        echo -e "${RED}✗${NC} $service: $status"
        return 1
    fi
}

check_postgres() {
    log_info "Checking PostgreSQL..."
    if docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} PostgreSQL: Ready"
        return 0
    else
        echo -e "${RED}✗${NC} PostgreSQL: Not ready"
        return 1
    fi
}

check_redis() {
    log_info "Checking Redis..."
    if docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Redis: Ready"
        return 0
    else
        echo -e "${RED}✗${NC} Redis: Not ready"
        return 1
    fi
}

check_backend_api() {
    log_info "Checking Backend API..."
    local response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/health 2>/dev/null || echo "000")

    if [ "$response" = "200" ]; then
        echo -e "${GREEN}✓${NC} Backend API: Healthy (HTTP $response)"
        return 0
    else
        echo -e "${RED}✗${NC} Backend API: Unhealthy (HTTP $response)"
        return 1
    fi
}

check_disk_space() {
    log_info "Checking disk space..."
    local usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')

    if [ "$usage" -lt 80 ]; then
        echo -e "${GREEN}✓${NC} Disk space: ${usage}% used"
        return 0
    elif [ "$usage" -lt 90 ]; then
        echo -e "${YELLOW}⚠${NC} Disk space: ${usage}% used (Warning)"
        return 0
    else
        echo -e "${RED}✗${NC} Disk space: ${usage}% used (Critical)"
        return 1
    fi
}

check_docker_volumes() {
    log_info "Checking Docker volumes..."
    local volumes=$(docker volume ls --format "{{.Name}}" | grep -c "forex" || echo "0")
    echo -e "${GREEN}✓${NC} Docker volumes: $volumes found"
}

show_resource_usage() {
    log_info "Resource usage:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" | grep forex || true
}

# Main health check
main() {
    echo "========================================="
    echo "  Forex Trading System - Health Check"
    echo "========================================="
    echo ""

    local failed=0

    log_info "Checking services..."
    check_service "postgres" || ((failed++))
    check_service "redis" || ((failed++))
    check_service "backend" || ((failed++))
    check_service "celery" || ((failed++))
    check_service "celery-beat" || ((failed++))
    check_service "frontend" || ((failed++))
    check_service "nginx" || ((failed++))

    echo ""
    check_postgres || ((failed++))
    check_redis || ((failed++))
    check_backend_api || ((failed++))

    echo ""
    check_disk_space || ((failed++))
    check_docker_volumes

    echo ""
    show_resource_usage

    echo ""
    echo "========================================="
    if [ $failed -eq 0 ]; then
        log_info "All health checks passed ✓"
        exit 0
    else
        log_error "$failed health check(s) failed ✗"
        exit 1
    fi
}

main
