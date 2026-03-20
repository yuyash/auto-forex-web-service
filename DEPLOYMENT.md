# Deployment

## Local Host

Use the development Compose file when you want to run the full stack on your own machine without the production image-pull and HTTPS setup.

### Prerequisites

- Docker Engine
- Docker Compose v2

### Local Environment File

Create `.env` at the repository root:

```dotenv
DB_PASSWORD=your_local_database_password
SECRET_KEY=your_local_django_secret_key
JWT_SECRET_KEY=your_local_jwt_secret_key
REDIS_PASSWORD=
DJANGO_ENV=development
```

Generate secrets locally if needed:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### Start the Local Stack

From the repository root:

```bash
docker compose build
docker compose up -d
```

The local stack uses [docker-compose.yaml](/home/yuyash/Workplace/AutoForex/docker-compose.yaml), builds images from the checked-out source, mounts the backend source code into the containers, and exposes HTTP only on port `80`.

### Initialize and Verify

Run these once after the first startup:

```bash
docker compose exec backend python manage.py createsuperuser
docker compose ps
docker compose logs -f
```

Default local endpoints:

- Frontend: `http://localhost`
- Backend API: `http://localhost/api`
- Django admin: `http://localhost/admin`
- Direct backend: `http://localhost:8000`

### Stop or Reset

```bash
docker compose down
docker compose down -v
```

Use `docker compose down -v` only when you intentionally want to delete the local PostgreSQL and Redis data.

## Production

The `Build and Deploy` GitHub Actions workflow builds Docker images, copies `docker-compose.prod.yaml` and `nginx/` to the host, and runs `docker compose pull && docker compose up -d`.

### Required GitHub Secrets

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`
- `SSH_PRIVATE_KEY`
- `SERVER_HOST`
- `SERVER_USER`
- `DEPLOY_PATH`
- `SSH_PORT` (optional, defaults to `22`)

### First-Time Host Setup

Before the first deployment, prepare the production host:

1. Install Docker Engine and Docker Compose v2.
2. Point your DNS records to the server and open inbound ports `80` and `443`.
3. Create the deployment directory and add a production `.env` file there.
4. Issue the initial Let's Encrypt certificate before relying on the HTTPS Nginx config.

Use this `.env` shape on the host at `<DEPLOY_PATH>/.env`:

```dotenv
DOCKERHUB_USERNAME=your-dockerhub-user
DB_PASSWORD=generate-a-strong-postgres-password
SECRET_KEY=generate-a-django-secret-key
JWT_SECRET_KEY=generate-a-different-jwt-secret-key
REDIS_PASSWORD=optional-redis-password
ALLOWED_HOSTS=www.yourdomain.com
```

Generate secrets locally if needed:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
python -c "import secrets; print(secrets.token_urlsafe(64))"
openssl rand -base64 48
```

Notes:

- `JWT_SECRET_KEY` must be set in production and must differ from `SECRET_KEY`.
- `DB_PASSWORD` must be correct before the first `docker compose up -d`. The PostgreSQL image uses it when initializing the database volume; changing it later requires an explicit password rotation procedure inside PostgreSQL.

### Initial Certificate Issuance

The production Nginx config expects real certificate files, so the first certificate issuance is a one-time manual step.

On the server:

```bash
mkdir -p <DEPLOY_PATH>/certbot/conf <DEPLOY_PATH>/certbot/www <DEPLOY_PATH>/certbot/work <DEPLOY_PATH>/certbot/logs <DEPLOY_PATH>/logs
cd <DEPLOY_PATH>
```

Install `certbot` on the host and obtain the initial certificate directly on the host instead of using Docker. The important part is to store the certificate under `<DEPLOY_PATH>/certbot/conf` so the production containers can mount the same files later.

```bash
sudo apt update
sudo apt install -y certbot

sudo certbot certonly --standalone \
  --preferred-challenges http \
  --config-dir <DEPLOY_PATH>/certbot/conf \
  --work-dir <DEPLOY_PATH>/certbot/work \
  --logs-dir <DEPLOY_PATH>/certbot/logs \
  -d www.yourdomain.com
```

Notes:

- `certbot --standalone` binds to port `80`, so nothing else should be listening on `80` during the first issuance.
- Because `--config-dir` points at `<DEPLOY_PATH>/certbot/conf`, the later Docker deployment can reuse the same certificate files without copying them again.
- After the first issuance, the repository's `certbot` container can continue renewing certificates against the same mounted certificate directory.

### Deploying with GitHub Actions

After the host is prepared:

1. Push to `main`.
2. The workflow creates required directories under `DEPLOY_PATH`, uploads the production Compose and Nginx files, validates that `<DEPLOY_PATH>/.env` exists, then deploys.
3. Verify the deployed services and TLS certificate on the host if this is the first run.
