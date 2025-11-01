# Auto Forex Trading System

A full-stack web application for managing algorithmic forex trading operations across multiple OANDA accounts with real-time market data streaming, strategy execution, position tracking, and comprehensive risk management.

## Features

- **Multi-Account Management**: Manage multiple OANDA accounts independently
- **Real-Time Market Data**: Live streaming of forex market data via OANDA v20 API
- **Modular Trading Strategies**: Plug-and-play strategy framework with Floor Strategy implementation
- **Risk Management**: ATR-based volatility protection and automatic margin monitoring
- **Position Tracking**: Real-time P&L calculation and position management
- **Backtesting Engine**: Test strategies against historical data from AWS S3/Athena
- **Admin Dashboard**: Comprehensive system monitoring and control
- **Event Logging**: Complete audit trail of all trading and system events
- **Internationalization**: Support for English and Japanese languages
- **Responsive Design**: Works on desktop and mobile devices

## Technology Stack

### Backend

- Django 5.2 LTS
- Django REST Framework
- Django Channels (WebSocket)
- PostgreSQL 17
- Redis 7
- Celery
- OANDA v20 Python library
- AWS boto3

### Frontend

- React 18
- TypeScript
- Vite
- Material-UI
- Lightweight Charts
- react-i18next

### Infrastructure

- Docker & Docker Compose
- Nginx with Let's Encrypt SSL
- GitHub Actions CI/CD

## Project Structure

```
.
├── backend/              # Django application
│   ├── apps/            # Django apps
│   ├── config/          # Django settings
│   ├── requirements.txt # Python dependencies
│   └── Dockerfile       # Backend container
├── frontend/            # React application
│   ├── src/            # React components
│   ├── package.json    # Node dependencies
│   └── Dockerfile      # Frontend container
├── nginx/              # Nginx configuration
│   ├── nginx.conf      # Nginx config
│   └── Dockerfile      # Nginx container
├── docker-compose.yaml # Docker Compose configuration
└── README.md          # This file
```

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Git

## Getting Started

### 1. Clone the Repository

```bash
git clone <repository-url>
cd auto-forex-trading-system
```

### 2. Environment Configuration

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` with your values. See [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md) for complete reference.

**Minimum required configuration:**

```bash
# Database
DB_NAME=forex_trading
DB_USER=postgres
DB_PASSWORD=your_secure_password

# Django
SECRET_KEY=your_secret_key_here_min_50_chars
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Security
ENCRYPTION_KEY=your_encryption_key_32_chars_min
```

**Generate secure keys:**

```bash
# Django SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Build and Start Services

```bash
# Build all containers
docker-compose build

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

### 4. Initialize Database

```bash
# Run migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec backend python manage.py createsuperuser
```

### 5. Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000/api
- **Admin Panel**: http://localhost:8000/admin

## Development

### Backend Development

```bash
# Enter backend container
docker-compose exec backend bash

# Run tests
pytest

# Run linting
flake8

# Format code
black .

# Type checking
mypy .
```

### Frontend Development

```bash
# Enter frontend container
docker-compose exec frontend sh

# Run tests
npm run test

# Run linting
npm run lint

# Format code
npm run format

# Type checking
npm run type-check
```

## Deployment

### Production Deployment

1. Update environment variables in `.env` for production
2. Set `DEBUG=False` in Django settings
3. Configure SSL certificates with Let's Encrypt
4. Update `docker-compose.yaml` for production settings
5. Deploy using GitHub Actions workflow

### SSL Configuration

```bash
# Generate SSL certificates
docker-compose run --rm certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  -d yourdomain.com \
  -d www.yourdomain.com
```

## Architecture

The system follows a microservices-inspired architecture:

- **Nginx**: Reverse proxy, SSL termination, static file serving
- **Django Backend**: REST API, WebSocket server, business logic
- **Celery Workers**: Asynchronous task processing, strategy execution
- **PostgreSQL**: Persistent data storage
- **Redis**: Caching, session storage, message broker
- **React Frontend**: User interface, real-time updates

## Trading Strategies

### Floor Strategy

The Floor Strategy implements multi-layer position management with dynamic scaling:

- **Scaling Modes**: Additive or multiplicative position sizing
- **Retracement Detection**: Automatic lot addition on K-pip retracements
- **Multi-Layer Management**: Up to 3 concurrent layers
- **Take-Profit Targets**: Configurable profit targets per layer
- **Risk Controls**: ATR-based volatility protection and margin monitoring

## Risk Management

### ATR-Based Volatility Protection

- Monitors 14-period ATR on 1-hour candles
- Triggers volatility lock when ATR ≥ 5x normal ATR
- Closes all positions at break-even prices
- Pauses strategy execution until volatility normalizes

### Margin Protection

- Calculates margin-liquidation ratio on every tick
- Automatically liquidates positions when ratio ≥ 100%
- Liquidates first lot of first layer, then second layer if needed
- Sends admin notifications on liquidation events

## Security

- JWT-based authentication with 24-hour expiration
- Password hashing with bcrypt
- Rate limiting (5 attempts per 15 minutes)
- IP-based blocking after failed login attempts
- Account locking after 10 failed attempts
- Encrypted storage of OANDA API tokens
- Role-based access control for admin endpoints
- Comprehensive security event logging

## Monitoring

### Admin Dashboard

- System health metrics (CPU, memory, database, Redis)
- Active user sessions
- Running strategies across all users
- Recent events and alerts
- Security monitoring

### Event Logging

All system events are logged with:

- Trading events (orders, positions, P&L)
- System events (connections, health checks)
- Security events (authentication, access attempts)
- Admin events (user management, strategy control)

## API Documentation

API documentation is available at:

- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Testing

### Backend Tests

```bash
# Run all tests
docker-compose exec backend pytest

# Run with coverage
docker-compose exec backend pytest --cov

# Run specific test file
docker-compose exec backend pytest tests/test_strategy.py
```

### Frontend Tests

```bash
# Run unit tests
docker-compose exec frontend npm run test

# Run E2E tests
docker-compose exec frontend npm run test:e2e
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or contributions, please open an issue on GitHub.

## Acknowledgments

- OANDA for providing the v20 API
- TradingView for Lightweight Charts library
- Django and React communities
