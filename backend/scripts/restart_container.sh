#!/bin/bash
# Script to restart the backend container
# This is triggered when debug mode or log level changes

CONTAINER_NAME="backend"

# Check if running in Docker
if [ -f /.dockerenv ]; then
    echo "Running inside Docker container"

    # Try to restart using docker-compose from host
    # This requires the container to have access to docker socket
    if command -v docker &> /dev/null; then
        echo "Restarting container: $CONTAINER_NAME"
        docker restart $CONTAINER_NAME 2>/dev/null || echo "Could not restart container automatically. Please restart manually."
    else
        echo "Docker command not available. Please restart the container manually."
    fi
else
    echo "Not running in Docker. Skipping restart."
fi
