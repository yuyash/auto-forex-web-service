#!/bin/bash

# Initialize Let's Encrypt SSL certificates for Auto Forex Trading System
# This script should be run once during initial setup

set -e

# Configuration
DOMAIN="${DOMAIN:-yourdomain.com}"
EMAIL="${EMAIL:-your-email@example.com}"
STAGING="${STAGING:-0}"  # Set to 1 for testing

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Let's Encrypt SSL Certificate Setup ===${NC}"
echo ""

# Check if domain is set
if [ "$DOMAIN" = "yourdomain.com" ]; then
    echo -e "${RED}Error: Please set your domain name${NC}"
    echo "Usage: DOMAIN=yourdomain.com EMAIL=your-email@example.com ./init-letsencrypt.sh"
    exit 1
fi

# Check if email is set
if [ "$EMAIL" = "your-email@example.com" ]; then
    echo -e "${RED}Error: Please set your email address${NC}"
    echo "Usage: DOMAIN=yourdomain.com EMAIL=your-email@example.com ./init-letsencrypt.sh"
    exit 1
fi

echo -e "${YELLOW}Domain: $DOMAIN${NC}"
echo -e "${YELLOW}Email: $EMAIL${NC}"
echo ""

# Create directories
echo -e "${GREEN}Creating certificate directories...${NC}"
mkdir -p certbot/conf/live/$DOMAIN
mkdir -p certbot/www

# Download recommended TLS parameters
echo -e "${GREEN}Downloading recommended TLS parameters...${NC}"
if [ ! -f "certbot/conf/options-ssl-nginx.conf" ]; then
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > certbot/conf/options-ssl-nginx.conf
fi

if [ ! -f "certbot/conf/ssl-dhparams.pem" ]; then
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem > certbot/conf/ssl-dhparams.pem
fi

# Create dummy certificate for nginx to start
echo -e "${GREEN}Creating dummy certificate for nginx...${NC}"
CERT_PATH="/etc/letsencrypt/live/$DOMAIN"
docker-compose run --rm --entrypoint "\
  openssl req -x509 -nodes -newkey rsa:4096 -days 1 \
    -keyout '$CERT_PATH/privkey.pem' \
    -out '$CERT_PATH/fullchain.pem' \
    -subj '/CN=localhost'" certbot

# Update nginx configuration with domain
echo -e "${GREEN}Updating nginx configuration...${NC}"
sed -i "s/your-domain.com/$DOMAIN/g" nginx/conf.d/default.conf

# Start nginx
echo -e "${GREEN}Starting nginx...${NC}"
docker-compose up -d nginx

# Delete dummy certificate
echo -e "${GREEN}Removing dummy certificate...${NC}"
docker-compose run --rm --entrypoint "\
  rm -rf /etc/letsencrypt/live/$DOMAIN && \
  rm -rf /etc/letsencrypt/archive/$DOMAIN && \
  rm -rf /etc/letsencrypt/renewal/$DOMAIN.conf" certbot

# Request Let's Encrypt certificate
echo -e "${GREEN}Requesting Let's Encrypt certificate...${NC}"

# Determine if we should use staging
STAGING_ARG=""
if [ "$STAGING" = "1" ]; then
    STAGING_ARG="--staging"
    echo -e "${YELLOW}Using Let's Encrypt staging server (test mode)${NC}"
fi

docker-compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email $EMAIL \
  --agree-tos \
  --no-eff-email \
  $STAGING_ARG \
  -d $DOMAIN \
  -d www.$DOMAIN

# Reload nginx
echo -e "${GREEN}Reloading nginx with new certificate...${NC}"
docker-compose exec nginx nginx -s reload

echo ""
echo -e "${GREEN}=== SSL Certificate Setup Complete ===${NC}"
echo ""
echo -e "${GREEN}Your site should now be accessible at:${NC}"
echo -e "${GREEN}  https://$DOMAIN${NC}"
echo -e "${GREEN}  https://www.$DOMAIN${NC}"
echo ""
echo -e "${YELLOW}Note: Certificates will auto-renew via the certbot service${NC}"
echo ""
