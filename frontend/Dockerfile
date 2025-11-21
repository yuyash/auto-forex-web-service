# Frontend Dockerfile for Auto Forex Trader
# Multi-stage build: Node for building, Nginx for serving

# Stage 1: Build the React application
FROM node:20-alpine AS builder

# Set work directory
WORKDIR /app

# Copy package files and npm config
COPY package*.json ./
COPY .npmrc ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

# Copy built files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
