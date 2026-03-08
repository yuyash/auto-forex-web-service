# Auto Forex Trader

A full-stack web application for managing algorithmic forex trading operations across multiple OANDA accounts with real-time market data streaming, strategy execution, position tracking, and comprehensive risk management.

## Features

- **Multi-Account Management**: Manage multiple OANDA accounts independently
- **Real-Time Market Data**: Live streaming of forex market data via OANDA v20 API
- **Modular Trading Strategies**: Plug-and-play strategy framework with Floor Strategy implementation
- **Risk Management**: ATR-based volatility protection and automatic margin monitoring
- **Position Tracking**: Real-time P&L calculation and position management
- **Backtesting Engine**: Test strategies against historical data from AWS S3/Athena
- **Event Logging**: Complete audit trail of all trading and system events

## Project Structure

```
.
├── backend/             # Django application
│   ├── apps/            # Django apps
│   ├── config/          # Django settings
│   ├── requirements.txt # Python dependencies
│   └── Dockerfile       # Backend container
├── frontend/            # React application
│   ├── src/             # React components
│   ├── package.json     # Node dependencies
│   └── Dockerfile       # Frontend container
├── nginx/               # Nginx configuration
│   ├── nginx.conf       # Nginx config
│   └── Dockerfile       # Nginx container
├── docker-compose.yaml  # Docker Compose configuration
└── README.md            # This file
```

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed local development setup instructions.

## Architecture

The system follows a microservices-inspired architecture:

- **Nginx**: Reverse proxy, SSL termination, static file serving
- **Django Backend**: REST API, WebSocket server, business logic
- **Celery Workers**: Asynchronous task processing, strategy execution
- **PostgreSQL**: Persistent data storage
- **Redis**: Caching, session storage, message broker
- **React Frontend**: User interface, real-time updates

## Risk Management

### ATR-Based Volatility Protection

- Monitors 14-period ATR on 1-hour candles
- Triggers volatility lock when ATR ≥ 5x normal ATR
- Closes all positions at break-even prices
- Stops strategy execution until volatility normalizes (can be resumed manually)

### Margin Protection

- Calculates margin-liquidation ratio on every tick
- Automatically liquidates positions when ratio ≥ 100%
- Liquidates first lot of first layer, then second layer if needed
- Sends admin notifications on liquidation events

## License

This project is licensed under the Apache-2.0 License - see the LICENSE file for details.
