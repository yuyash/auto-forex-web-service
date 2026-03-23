# Frontend Dockerfile for Auto Forex Trader
# Multi-stage build: Node for building, Nginx for serving
#
# The builder stage is pinned to linux/amd64 because it only produces
# static files (HTML/JS/CSS) that are architecture-independent.
# This avoids slow QEMU emulation of Node.js during multi-arch builds.

# Stage 1: Build the React application (always on amd64 — output is static files)
FROM --platform=linux/amd64 node:20-alpine AS builder

# Set work directory
WORKDIR /app

# Copy package files and npm config first (better layer caching)
COPY package*.json .npmrc ./

# Install dependencies with cache mount for faster rebuilds
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Stage 2: Serve with Nginx (multi-arch — inherits target platform)
FROM nginx:alpine

# Copy built files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
