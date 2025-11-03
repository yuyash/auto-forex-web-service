#!/bin/bash
# Test script to validate nginx configuration
# This script should be run inside the nginx container

echo "Testing nginx configuration..."

# Test configuration syntax
nginx -t

if [ $? -eq 0 ]; then
    echo "✓ Nginx configuration is valid"
    exit 0
else
    echo "✗ Nginx configuration has errors"
    exit 1
fi
