#!/bin/bash
# View logs from services
# Usage: ./logs.sh [service] [options]

set -e

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yaml}"

show_usage() {
    echo "Usage: $0 [service] [options]"
    echo ""
    echo "Services:"
    echo "  all       - All services (default)"
    echo "  backend   - Django backend"
    echo "  celery    - Celery worker"
    echo "  beat      - Celery beat scheduler"
    echo "  frontend  - React frontend"
    echo "  nginx     - Nginx reverse proxy"
    echo "  postgres  - PostgreSQL database"
    echo "  redis     - Redis cache"
    echo ""
    echo "Options:"
    echo "  -f, --follow    Follow log output"
    echo "  -n, --tail N    Number of lines to show (default: 100)"
    echo ""
    echo "Examples:"
    echo "  $0 backend -f"
    echo "  $0 celery --tail 50"
    echo "  $0 all --follow"
    exit 1
}

# Parse arguments
SERVICE="${1:-all}"
shift || true

FOLLOW=""
TAIL="100"

while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW="-f"
            shift
            ;;
        -n|--tail)
            TAIL="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            ;;
    esac
done

# Map service names
case "$SERVICE" in
    all)
        docker compose -f "$COMPOSE_FILE" logs $FOLLOW --tail="$TAIL"
        ;;
    backend)
        docker compose -f "$COMPOSE_FILE" logs $FOLLOW --tail="$TAIL" backend
        ;;
    celery)
        docker compose -f "$COMPOSE_FILE" logs $FOLLOW --tail="$TAIL" celery
        ;;
    beat|celery-beat)
        docker compose -f "$COMPOSE_FILE" logs $FOLLOW --tail="$TAIL" celery-beat
        ;;
    frontend)
        docker compose -f "$COMPOSE_FILE" logs $FOLLOW --tail="$TAIL" frontend
        ;;
    nginx)
        docker compose -f "$COMPOSE_FILE" logs $FOLLOW --tail="$TAIL" nginx
        ;;
    postgres)
        docker compose -f "$COMPOSE_FILE" logs $FOLLOW --tail="$TAIL" postgres
        ;;
    redis)
        docker compose -f "$COMPOSE_FILE" logs $FOLLOW --tail="$TAIL" redis
        ;;
    *)
        echo "Unknown service: $SERVICE"
        show_usage
        ;;
esac
