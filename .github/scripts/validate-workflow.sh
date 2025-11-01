#!/bin/bash

# Workflow validation script
# Validates GitHub Actions workflow files and checks for common issues

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if workflow file exists
check_workflow_exists() {
    if [ ! -f .github/workflows/build-and-deploy.yml ]; then
        print_error "Workflow file not found: .github/workflows/build-and-deploy.yml"
        exit 1
    fi
    print_info "Workflow file found"
}

# Validate YAML syntax
validate_yaml_syntax() {
    print_info "Validating YAML syntax..."
    
    if command -v yamllint &> /dev/null; then
        yamllint .github/workflows/build-and-deploy.yml || {
            print_error "YAML syntax validation failed"
            exit 1
        }
        print_info "YAML syntax is valid"
    else
        print_warning "yamllint not installed - skipping YAML validation"
        print_info "Install with: pip install yamllint"
    fi
}

# Check for required secrets in workflow
check_required_secrets() {
    print_info "Checking for required secrets..."
    
    local workflow_file=".github/workflows/build-and-deploy.yml"
    local required_secrets=(
        "DOCKERHUB_USERNAME"
        "DOCKERHUB_TOKEN"
        "SSH_PRIVATE_KEY"
        "SERVER_HOST"
        "SERVER_USER"
        "DEPLOY_PATH"
    )
    
    local missing_secrets=()
    
    for secret in "${required_secrets[@]}"; do
        if ! grep -q "secrets\.${secret}" "$workflow_file"; then
            missing_secrets+=("$secret")
        fi
    done
    
    if [ ${#missing_secrets[@]} -ne 0 ]; then
        print_warning "The following secrets are not referenced in the workflow:"
        for secret in "${missing_secrets[@]}"; do
            echo "  - $secret"
        done
    else
        print_info "All required secrets are referenced"
    fi
}

# Validate Docker Compose configuration
validate_docker_compose() {
    print_info "Validating Docker Compose configuration..."
    
    if [ ! -f docker-compose.yaml ]; then
        print_error "docker-compose.yaml not found"
        exit 1
    fi
    
    # Check if .env file exists
    if [ ! -f .env ]; then
        print_warning "No .env file found - Docker Compose validation may fail"
        print_info "Create .env from .env.example if needed"
        return 0
    fi
    
    # Validate with environment variables
    docker compose config > /dev/null 2>&1 || {
        print_warning "Docker Compose configuration validation failed"
        print_info "This may be due to missing environment variables"
        print_info "Ensure .env file is properly configured for deployment"
        return 0
    }
    
    print_info "Docker Compose configuration is valid"
}

# Check Dockerfile existence
check_dockerfiles() {
    print_info "Checking for Dockerfiles..."
    
    local dockerfiles=(
        "backend/Dockerfile"
        "frontend/Dockerfile"
        "nginx/Dockerfile.prod"
    )
    
    local missing_files=()
    
    for dockerfile in "${dockerfiles[@]}"; do
        if [ ! -f "$dockerfile" ]; then
            missing_files+=("$dockerfile")
        fi
    done
    
    if [ ${#missing_files[@]} -ne 0 ]; then
        print_error "Missing Dockerfiles:"
        for file in "${missing_files[@]}"; do
            echo "  - $file"
        done
        exit 1
    else
        print_info "All Dockerfiles found"
    fi
}

# Check workflow triggers
check_workflow_triggers() {
    print_info "Checking workflow triggers..."
    
    local workflow_file=".github/workflows/build-and-deploy.yml"
    
    if grep -q "on:" "$workflow_file" && grep -q "push:" "$workflow_file"; then
        print_info "Workflow has push trigger configured"
    else
        print_warning "Workflow may not have push trigger configured"
    fi
    
    if grep -q "pull_request:" "$workflow_file"; then
        print_info "Workflow has pull request trigger configured"
    else
        print_warning "Workflow does not have pull request trigger"
    fi
}

# Check for deployment conditions
check_deployment_conditions() {
    print_info "Checking deployment conditions..."
    
    local workflow_file=".github/workflows/build-and-deploy.yml"
    
    if grep -q "if:.*main" "$workflow_file"; then
        print_info "Deployment is conditional on main branch"
    else
        print_warning "Deployment may not be restricted to main branch"
    fi
}

# Summary
print_summary() {
    echo ""
    echo "================================"
    echo "Validation Summary"
    echo "================================"
    print_info "✅ Workflow validation completed"
    echo ""
    print_info "Next steps:"
    echo "  1. Configure GitHub secrets (see .github/README.md)"
    echo "  2. Test workflow by pushing to a branch"
    echo "  3. Monitor workflow execution in GitHub Actions tab"
    echo ""
}

# Main validation flow
main() {
    print_info "Starting workflow validation..."
    echo ""
    
    check_workflow_exists
    validate_yaml_syntax
    check_required_secrets
    validate_docker_compose
    check_dockerfiles
    check_workflow_triggers
    check_deployment_conditions
    
    print_summary
}

main
