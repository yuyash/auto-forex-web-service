# Docker Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           INTERNET                                   │
│                    (Port 443 via Router)                            │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      NGINX CONTAINER                                 │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  • SSL Termination (Let's Encrypt)                             │ │
│  │  • Reverse Proxy                                               │ │
│  │  • Rate Limiting (100 req/min API, 5 req/min login)          │ │
│  │  • Static File Serving                                         │ │
│  │  • WebSocket Proxy                                             │ │
│  │  • Security Headers                                            │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                    Ports: 80 (HTTP), 443 (HTTPS)                    │
└────────────┬────────────────────┬──────────────────┬────────────────┘
             │                    │                  │
             │ /api/*             │ /ws/*            │ /*
             │                    │                  │
    ┌────────▼────────┐  ┌───────▼────────┐  ┌─────▼──────┐
    │                 │  │                 │  │            │
    │  BACKEND        │  │  WEBSOCKET      │  │  FRONTEND  │
    │  (Django)       │  │  (Channels)     │  │  (React)   │
    │                 │  │                 │  │            │
    │  Port: 8000     │  │  Port: 8000     │  │  Port: 80  │
    │  (Daphne ASGI)  │  │  (Same as API)  │  │  (Nginx)   │
    └────────┬────────┘  └───────┬─────────┘  └────────────┘
             │                   │
             │                   │
    ┌────────┴───────────────────┴────────┐
    │                                      │
    │  ┌──────────────┐  ┌──────────────┐ │
    │  │              │  │              │ │
    │  │  POSTGRES    │  │    REDIS     │ │
    │  │  Database    │  │  Cache/Broker│ │
    │  │              │  │              │ │
    │  │  Port: 5432  │  │  Port: 6379  │ │
    │  │  Volume:     │  │  Volume:     │ │
    │  │  postgres_   │  │  redis_data  │ │
    │  │  data        │  │              │ │
    │  └──────────────┘  └──────────────┘ │
    │                                      │
    └──────────────────┬───────────────────┘
                       │
                       │
    ┌──────────────────┴───────────────────┐
    │                                       │
    │  ┌──────────────┐  ┌──────────────┐  │
    │  │              │  │              │  │
    │  │   CELERY     │  │ CELERY-BEAT  │  │
    │  │   WORKER     │  │  SCHEDULER   │  │
    │  │              │  │              │  │
    │  │  • Market    │  │  • Periodic  │  │
    │  │    Data      │  │    Tasks     │  │
    │  │  • Strategy  │  │  • Health    │  │
    │  │    Execution │  │    Checks    │  │
    │  │  • Backtest  │  │  • Balance   │  │
    │  │  • Risk Mgmt │  │    Updates   │  │
    │  └──────────────┘  └──────────────┘  │
    │                                       │
    └───────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      CERTBOT CONTAINER                               │
│  • SSL Certificate Renewal (every 12 hours)                         │
│  • Let's Encrypt ACME Challenge                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagrams

### 1. User Authentication Flow

```
User Browser
     │
     │ POST /api/auth/login
     ▼
   Nginx (Rate Limit: 5/min)
     │
     │ Proxy to Backend
     ▼
  Django Backend
     │
     ├─► Validate Credentials (PostgreSQL)
     │
     ├─► Generate JWT Token
     │
     ├─► Log Event (PostgreSQL)
     │
     └─► Return Token
         │
         ▼
    User Browser (Store Token)
```

### 2. Real-Time Market Data Flow

```
OANDA v20 API
     │
     │ Streaming Connection
     ▼
Celery Worker (Market Data Task)
     │
     ├─► Process Tick Data
     │
     ├─► Update Redis Cache
     │
     ├─► Trigger Strategy Execution
     │
     └─► Broadcast via Channels
         │
         ▼
    Django Channels (WebSocket)
         │
         │ wss://domain/ws/market-data/
         ▼
    User Browser (Update Chart)
```

### 3. Order Execution Flow

```
Strategy Signal
     │
     ▼
Celery Worker
     │
     ├─► Validate Order
     │
     ├─► Submit to OANDA API
     │
     ├─► Retry on Failure (3x)
     │
     ├─► Update Position (PostgreSQL)
     │
     ├─► Log Event (PostgreSQL)
     │
     └─► Broadcast Update (WebSocket)
         │
         ▼
    User Browser (Update UI)
```

### 4. Backtesting Flow

```
User Request
     │
     │ POST /api/backtest/start
     ▼
  Django Backend
     │
     ├─► Create Backtest Record (PostgreSQL)
     │
     └─► Queue Celery Task
         │
         ▼
    Celery Worker
         │
         ├─► Load Historical Data (S3/Athena)
         │
         ├─► Execute Strategy Simulation
         │
         ├─► Calculate Metrics
         │
         ├─► Store Results (PostgreSQL)
         │
         └─► Notify User (WebSocket)
             │
             ▼
        User Browser (View Results)
```

## Network Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Network: forex_network             │
│                         (Bridge Mode)                        │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Nginx   │  │ Backend  │  │ Frontend │  │ Postgres │   │
│  │          │  │          │  │          │  │          │   │
│  │ 80, 443  │  │   8000   │  │    80    │  │   5432   │   │
│  └────┬─────┘  └────┬─────┘  └──────────┘  └────┬─────┘   │
│       │             │                            │          │
│       └─────────────┴────────────────────────────┘          │
│                     │                                        │
│  ┌──────────┐  ┌───┴──────┐  ┌──────────┐  ┌──────────┐   │
│  │  Redis   │  │  Celery  │  │  Celery  │  │ Certbot  │   │
│  │          │  │  Worker  │  │   Beat   │  │          │   │
│  │   6379   │  │          │  │          │  │          │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
         │                                          │
         │ Exposed Ports                            │
         ▼                                          ▼
    Host: 80, 443                          Host: 5432, 6379
    (Production)                           (Development Only)
```

## Volume Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Volumes                          │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │  postgres_data   │  │   redis_data     │                │
│  │                  │  │                  │                │
│  │  • Database      │  │  • Cache         │                │
│  │    Files         │  │  • Sessions      │                │
│  │  • Persistent    │  │  • AOF Log       │                │
│  └────────┬─────────┘  └────────┬─────────┘                │
│           │                     │                           │
│           ▼                     ▼                           │
│      PostgreSQL              Redis                          │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │  static_volume   │  │  media_volume    │                │
│  │                  │  │                  │                │
│  │  • CSS/JS        │  │  • User Uploads  │                │
│  │  • Images        │  │  • Documents     │                │
│  └────────┬─────────┘  └────────┬─────────┘                │
│           │                     │                           │
│           └──────────┬──────────┘                           │
│                      ▼                                       │
│                    Nginx                                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      Bind Mounts                             │
│                                                              │
│  Host: ./certbot/conf  ←→  Container: /etc/letsencrypt     │
│  Host: ./certbot/www   ←→  Container: /var/www/certbot     │
│  Host: ./config        ←→  Container: /app/config          │
│  Host: ./logs          ←→  Container: /app/logs            │
│  Host: ./backend       ←→  Container: /app (dev only)      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Service Dependencies

```
┌─────────────────────────────────────────────────────────────┐
│                    Service Start Order                       │
│                                                              │
│  1. postgres (with health check)                            │
│     └─► Wait until healthy                                  │
│                                                              │
│  2. redis (with health check)                               │
│     └─► Wait until healthy                                  │
│                                                              │
│  3. backend (depends on postgres + redis)                   │
│     └─► Run migrations                                      │
│     └─► Collect static files                                │
│     └─► Start Daphne server                                 │
│                                                              │
│  4. celery (depends on backend + redis)                     │
│     └─► Start worker processes                              │
│                                                              │
│  5. celery-beat (depends on backend + redis)                │
│     └─► Start scheduler                                     │
│                                                              │
│  6. frontend (depends on backend)                           │
│     └─► Serve built React app                               │
│                                                              │
│  7. nginx (depends on backend + frontend)                   │
│     └─► Start reverse proxy                                 │
│                                                              │
│  8. certbot (independent)                                   │
│     └─► Renew certificates periodically                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Resource Allocation

```
┌─────────────────────────────────────────────────────────────┐
│                  Recommended Resources                       │
│                                                              │
│  Service         CPU      Memory    Disk      Priority      │
│  ──────────────────────────────────────────────────────────│
│  postgres        1-2      1-2 GB    10 GB     High         │
│  redis           0.5-1    512 MB    1 GB      High         │
│  backend         1-2      1-2 GB    5 GB      High         │
│  celery          2-4      2-4 GB    2 GB      High         │
│  celery-beat     0.5      256 MB    1 GB      Medium       │
│  frontend        0.5      256 MB    1 GB      Low          │
│  nginx           0.5-1    256 MB    1 GB      High         │
│  certbot         0.1      128 MB    500 MB    Low          │
│  ──────────────────────────────────────────────────────────│
│  TOTAL           6-12     5-10 GB   21.5 GB                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Security Layers

```
┌─────────────────────────────────────────────────────────────┐
│                      Security Stack                          │
│                                                              │
│  Layer 1: Network                                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  • Firewall (only 80, 443 exposed)                     │ │
│  │  • Docker network isolation                             │ │
│  │  • No direct database access from internet             │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Layer 2: Transport                                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  • TLS 1.2/1.3 encryption                              │ │
│  │  • Let's Encrypt certificates                           │ │
│  │  • HSTS enabled                                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Layer 3: Application                                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  • Rate limiting (Nginx)                               │ │
│  │  • JWT authentication                                   │ │
│  │  • CSRF protection                                      │ │
│  │  • XSS protection headers                               │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Layer 4: Data                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  • Encrypted API tokens (Fernet)                       │ │
│  │  • Hashed passwords (bcrypt)                            │ │
│  │  • Encrypted volumes (optional)                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Deployment Environments

### Development

```
┌─────────────────────────────────────────────────────────────┐
│                    Development Setup                         │
│                                                              │
│  • HTTP only (no SSL)                                       │
│  • Debug mode enabled                                       │
│  • Hot reload for code changes                              │
│  • Exposed database ports                                   │
│  • Verbose logging                                          │
│  • Local file mounts                                        │
│                                                              │
│  Access: http://localhost                                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Production

```
┌─────────────────────────────────────────────────────────────┐
│                    Production Setup                          │
│                                                              │
│  • HTTPS with Let's Encrypt                                 │
│  • Debug mode disabled                                      │
│  • Optimized builds                                         │
│  • No exposed database ports                                │
│  • Error-level logging                                      │
│  • Volume-only mounts                                       │
│  • Rate limiting enforced                                   │
│  • Automated backups                                        │
│  • Health monitoring                                        │
│                                                              │
│  Access: https://yourdomain.com                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Scaling Strategy

### Horizontal Scaling

```
┌─────────────────────────────────────────────────────────────┐
│                  Scalable Components                         │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Celery Workers (Stateless)                          │  │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐    │  │
│  │  │Worker 1│  │Worker 2│  │Worker 3│  │Worker N│    │  │
│  │  └────────┘  └────────┘  └────────┘  └────────┘    │  │
│  │  Scale: docker-compose up -d --scale celery=N       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Backend Instances (with Load Balancer)              │  │
│  │  ┌────────┐  ┌────────┐  ┌────────┐                │  │
│  │  │Backend1│  │Backend2│  │Backend3│                │  │
│  │  └────────┘  └────────┘  └────────┘                │  │
│  │  Requires: External load balancer configuration      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Vertical Scaling

```
┌─────────────────────────────────────────────────────────────┐
│                  Resource Limits                             │
│                                                              │
│  Add to docker-compose.yaml:                                │
│                                                              │
│  services:                                                  │
│    backend:                                                 │
│      deploy:                                                │
│        resources:                                           │
│          limits:                                            │
│            cpus: '2'                                        │
│            memory: 2G                                       │
│          reservations:                                      │
│            cpus: '1'                                        │
│            memory: 1G                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Monitoring Points

```
┌─────────────────────────────────────────────────────────────┐
│                    Health Check Endpoints                    │
│                                                              │
│  • /api/health              - Backend health                │
│  • /api/admin/health        - System metrics                │
│  • PostgreSQL health check  - pg_isready                    │
│  • Redis health check       - redis-cli ping                │
│  • Nginx status             - nginx -t                      │
│  • Celery worker status     - celery inspect active         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

This architecture provides a robust, scalable, and secure foundation for the Auto Forex Trader.
