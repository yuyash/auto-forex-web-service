#!/bin/bash

# Deployment script for Auto Forex Trading System
# This script can be used for manual deployments or as a reference for CI/CD

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required environment variables are set
check_env_vars() {
    local required_vars=("SERVER_HOST" "SERVER_USER" "DEPLOY_PATH")
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -ne 0 ]; then
        print_error "Missing required environment variables: ${missing_vars[*]}"
        print_info "Please set the following variables:"
        print_info "  export SERVER_HOST=your-server-host"
        print_info "  export SERVER_USER=your-ssh-user"
        print_info "  export DEPLOY_PATH=/path/to/deployment"
        print_info "  export SSH_PORT=22 (optional, defaults to 22)"
        exit 1
    fi
    
    # Set default SSH port if not specified
    if [ -z "${SSH_PORT}" ]; then
        SSH_PORT=22
        print_info "SSH_PORT not set, using default: 22"
    else
        print_info "Using SSH port: ${SSH_PORT}"
    fi
}

# Test SSH connection
test_ssh_connection() {
    print_info "Testing SSH connection to ${SERVER_USER}@${SERVER_HOST}:${SSH_PORT}..."
    
    if ssh -p "${SSH_PORT}" -o ConnectTimeout=10 -o BatchMode=yes "${SERVER_USER}@${SERVER_HOST}" "echo 'SSH connection successful'" > /dev/null 2>&1; then
        print_info "SSH connection successful"
    else
        print_error "Failed to connect to ${SERVER_USER}@${SERVER_HOST}:${SSH_PORT}"
        print_info "Please ensure:"
        print_info "  1. SSH key is added to ssh-agent: ssh-add ~/.ssh/your-key"
        print_info "  2. Server is reachable: ping ${SERVER_HOST}"
        print_info "  3. SSH key is authorized on server"
        print_info "  4. SSH port ${SSH_PORT} is correct and open"
        exit 1
    fi
}

# Copy files to server
copy_files() {
    print_info "Copying files to server..."
    
    # Check if docker-compose.prod.yaml exists
    if [ ! -f docker-compose.prod.yaml ]; then
        print_error "docker-compose.prod.yaml not found"
        exit 1
    fi
    
    # Copy docker-compose.prod.yaml as docker-compose.yaml
    print_info "Copying docker-compose.prod.yaml as docker-compose.yaml..."
    scp -P "${SSH_PORT}" docker-compose.prod.yaml "${SERVER_USER}@${SERVER_HOST}:${DEPLOY_PATH}/docker-compose.yaml" || {
        print_error "Failed to copy docker-compose.prod.yaml"
        exit 1
    }
    
    # Copy nginx configuration
    scp -P "${SSH_PORT}" -r nginx "${SERVER_USER}@${SERVER_HOST}:${DEPLOY_PATH}/" || {
        print_error "Failed to copy nginx configuration"
        exit 1
    }
    
    # Copy .env file if it exists
    if [ -f .env ]; then
        print_warning "Copying .env file - ensure it contains production values"
        scp -P "${SSH_PORT}" .env "${SERVER_USER}@${SERVER_HOST}:${DEPLOY_PATH}/" || {
            print_error "Failed to copy .env file"
            exit 1
        }
    else
        print_warning ".env file not found - ensure it exists on the server"
    fi
    
    print_info "Files copied successfully"
}

# Deploy application
deploy_application() {
    print_info "Deploying application on server..."
    
    ssh -p "${SSH_PORT}" "${SERVER_USER}@${SERVER_HOST}" << EOF
        set -e
        cd ${DEPLOY_PATH}
        
        echo "Pulling latest Docker images..."
        docker compose pull
        
        echo "Stopping old containers..."
        docker compose down
        
        echo "Starting new containers..."
        docker compose up -d
        
        echo "Waiting for services to start..."
        sleep 10
        
        echo "Checking service status..."
        docker compose ps
        
        echo "Cleaning up old images..."
        docker image prune -af
        
        echo "Deployment completed"
EOF
    
    if [ $? -eq 0 ]; then
        print_info "Deployment successful"
    else
        print_error "Deployment failed"
        exit 1
    fi
}

# Verify deployment
verify_deployment() {
    print_info "Verifying deployment..."
    
    ssh -p "${SSH_PORT}" "${SERVER_USER}@${SERVER_HOST}" << EOF
        set -e
        cd ${DEPLOY_PATH}
        
        # Check if containers are running
        if docker compose ps | grep -q "Up"; then
            echo "✅ All services are running"
            docker compose ps
            exit 0
        else
            echo "❌ Some services are not running"
            docker compose ps
            echo ""
            echo "Recent logs:"
            docker compose logs --tail=50
            exit 1
        fi
EOF
    
    if [ $? -eq 0 ]; then
        print_info "Verification successful"
    else
        print_error "Verification failed - check logs above"
        exit 1
    fi
}

# Rollback to previous version
rollback() {
    print_warning "Rolling back to previous version..."
    
    ssh -p "${SSH_PORT}" "${SERVER_USER}@${SERVER_HOST}" << EOF
        set -e
        cd ${DEPLOY_PATH}
        
        echo "Stopping current containers..."
        docker compose down
        
        echo "Starting previous version..."
        # This assumes you have a backup of the previous docker-compose.yaml
        if [ -f docker-compose.yaml.backup ]; then
            cp docker-compose.yaml.backup docker-compose.yaml
            docker compose up -d
            echo "Rollback completed"
        else
            echo "No backup found - manual intervention required"
            exit 1
        fi
EOF
}

# Main deployment flow
main() {
    print_info "Starting deployment process..."
    print_info "Target: ${SERVER_USER}@${SERVER_HOST}:${SSH_PORT}:${DEPLOY_PATH}"
    
    check_env_vars
    test_ssh_connection
    copy_files
    deploy_application
    verify_deployment
    
    print_info "🎉 Deployment completed successfully!"
}

# Handle script arguments
case "${1:-deploy}" in
    deploy)
        main
        ;;
    rollback)
        rollback
        ;;
    verify)
        check_env_vars
        verify_deployment
        ;;
    test-ssh)
        check_env_vars
        test_ssh_connection
        ;;
    *)
        echo "Usage: $0 {deploy|rollback|verify|test-ssh}"
        echo ""
        echo "Commands:"
        echo "  deploy    - Deploy the application (default)"
        echo "  rollback  - Rollback to previous version"
        echo "  verify    - Verify current deployment"
        echo "  test-ssh  - Test SSH connection"
        echo ""
        echo "Required environment variables:"
        echo "  SERVER_HOST  - Production server hostname or IP"
        echo "  SERVER_USER  - SSH username"
        echo "  DEPLOY_PATH  - Deployment directory path"
        echo "  SSH_PORT     - SSH port (optional, defaults to 22)"
        echo ""
        echo "Example:"
        echo "  export SERVER_HOST=example.com"
        echo "  export SERVER_USER=deploy"
        echo "  export DEPLOY_PATH=/opt/forex-trading"
        echo "  export SSH_PORT=2222"
        echo "  $0 deploy"
        exit 1
        ;;
esac
