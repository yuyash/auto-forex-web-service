# Nginx Dockerfile with SSL support for Auto Forex Trading System

FROM nginx:alpine

# Install certbot for Let's Encrypt SSL certificates
RUN apk add --no-cache certbot certbot-nginx

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf
COPY conf.d/ /etc/nginx/conf.d/

# Create directories for SSL certificates and challenges
RUN mkdir -p /var/www/certbot /etc/letsencrypt

# Expose HTTP and HTTPS ports
EXPOSE 80 443

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
