# WordleStack

**WordleStack** is a self-hosted daily Wordle competition platform. Play the daily puzzle, compare results with friends, and compete in private Leagues.

## Requirements

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/) (Compose v2)

## Setup

### 1. Create a directory

```bash
mkdir wordlestack && cd wordlestack
```

### 2. Create the configuration files

```bash
touch compose.yaml .env
```

### 3. Configure Docker Compose

Add the following to `compose.yaml`:

```yaml
services:
  app:
    image: ghcr.io/jashan7305/wordlestack:latest
    container_name: wordlestack
    restart: unless-stopped

    ports:
      - "${APP_PORT:-8002}:8000"

    environment:
      APP_NAME: WordleStack
      DEBUG: "false"
      TIMEZONE: ${TIMEZONE:-Asia/Kolkata}

      DATABASE_URL: postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}

      SECRET_KEY: ${SECRET_KEY}
      ADMIN_USERNAME: ${ADMIN_USERNAME}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD}

      COOKIE_SECURE: ${COOKIE_SECURE:-false}
      CORS_ORIGINS: ${CORS_ORIGINS:-http://localhost:8002}
      PUBLIC_URL: ${PUBLIC_URL:-http://localhost:8002}

    depends_on:
      db:
        condition: service_healthy

    healthcheck:
      test:
        - CMD
        - python
        - -c
        - "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s

  db:
    image: postgres:18
    container_name: wordlestack-db
    restart: unless-stopped

    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}

    volumes:
      - wordlestack_data:/var/lib/postgresql

    healthcheck:
      test:
        - CMD-SHELL
        - pg_isready -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  wordlestack_data:
```

### 4. Configure environment variables

Add the following to `.env`:

```dotenv
# Application
APP_NAME=WordleStack
DEBUG=false
TIMEZONE=Asia/Kolkata
APP_PORT=8002
PUBLIC_URL=http://localhost:8002

# Database
DB_NAME=wordlestack
DB_USER=wordlestack
DB_PASSWORD=replace_with_secure_password

DATABASE_URL=postgresql+psycopg://wordlestack:replace_with_secure_password@db:5432/wordlestack

# Security
SECRET_KEY=replace_with_a_long_random_secret

# Initial administrator
ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace_with_a_secure_admin_password

# CORS
CORS_ORIGINS=http://localhost:8002
```

**Important:** Replace the database password, secret key, and administrator password before starting the application.

You can generate secure random values using:

```bash
openssl rand -hex 32
```

Generate a separate value for `DB_PASSWORD` and `SECRET_KEY`.

### 5. Start WordleStack

Pull the latest image and start the containers:

```bash
docker compose pull
docker compose up -d
```

### 6. Access WordleStack

Open the following address in your browser:

```text
http://localhost:8002
```

If you changed `APP_PORT`, use the corresponding port instead.

## Managing WordleStack

**View application logs:**

```bash
docker compose logs -f app
```

**View all container logs:**

```bash
docker compose logs -f
```

**Stop WordleStack:**

```bash
docker compose down
```

**Update to the latest version:**

```bash
docker compose pull
docker compose up -d
```