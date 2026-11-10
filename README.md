# WordleStack

WordleStack is a self-hosted daily Wordle competition for private Leagues. Players get one game per official NYT puzzle date; that result is shared across every League and counted once in personal and global statistics.

## Architecture

- FastAPI modular monolith, SQLAlchemy 2, PostgreSQL, and Alembic.
- React, TypeScript, Vite, and Tailwind CSS v4 frontend.
- One application container serves the compiled frontend and JSON API; PostgreSQL stores accounts, puzzles, games, guesses, Leagues, memberships, invitations, and statistics.
- The app retrieves the official puzzle from the NYT daily endpoint and stores it by the provider's `print_date`. A PostgreSQL advisory lock coordinates periodic synchronization between app workers.
- The backend scores guesses and games. The frontend never receives the answer until the game is complete.
- Authentication and invitation lookup endpoints have per-IP request limits in the app process. If you run multiple app workers, enforce the same limits at a shared reverse proxy.

## Features

Daily Wordle gameplay, USER and ADMIN roles, cookie authentication, League memberships, daily and overall League boards, global standings, guess history, personal statistics, and invitation links. Practice mode and configurable answers are not part of this release.

## Prerequisites

- Docker and Docker Compose for the complete deployment.
- Python 3.13 and uv for backend development.
- Node.js 22 and pnpm for frontend development.

## Environment

Copy `.env.example` to `.env`, then set strong unique values for `DB_PASSWORD`, `SECRET_KEY`, and `ADMIN_PASSWORD`. The root `.env` is ignored by Git. `TIMEZONE` defaults to `Asia/Kolkata`; `PUBLIC_URL` must be the site's public base URL for invitation links; `COOKIE_SECURE=true` should be used behind HTTPS. Set `DATABASE_URL` to `postgresql+psycopg://...@localhost:5432/...` for local backend development. Compose uses the `db` hostname.

## Docker deployment

```sh
docker compose up -d --build
```

Open <http://localhost:8080>. The initial `ADMIN_USERNAME` and `ADMIN_PASSWORD` create an administrator on first startup only; changing those variables does not reset an existing account. PostgreSQL data persists in the `wordlestack_data` volume. Alembic migrations run before the app server starts.

To stop the service while retaining data, run `docker compose down`. To delete persistent data as well, explicitly remove the volume with `docker compose down -v`.

## Local development

Start only PostgreSQL with `docker compose up -d db`.

Backend:

```sh
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Frontend, in a second terminal:

```sh
cd frontend
pnpm install
pnpm dev
```

Vite proxies `/api` to `http://localhost:8000`. API documentation is available at `/docs` while running the backend.

## Database operations

Run migrations with `cd backend && uv run alembic upgrade head`. Back up the Compose database with:

```sh
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > wordlestack.sql
```

Restore into an empty database with:

```sh
cat wordlestack.sql | docker compose exec -T db psql -U "$DB_USER" "$DB_NAME"
```

Set `DB_USER` and `DB_NAME` in the shell before these commands.

## Quality checks

```sh
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm test && pnpm lint && pnpm typecheck && pnpm build
```

The NYT provider is an external dependency. Previously cached puzzle dates remain available when it is offline; a date that has never been cached cannot be played until the provider responds. Guess validation uses 7,062 five-letter entries from SCOWL 2020.12.07. Its source, filtering, and license notices are documented in `backend/app/data/README.md` and `SCOWL-Copyright`. The puzzle answer itself is always from NYT.

## Troubleshooting

- If the app cannot connect to Postgres, check container health and ensure app configuration uses host `db` in Compose or `localhost` locally.
- If login fails after changing admin environment values, the stored administrator password was deliberately left unchanged; sign in with the existing password.
- If today's puzzle cannot load, check outbound access to the NYT puzzle endpoint. Cached earlier puzzle dates are not removed on provider errors.
- For development over plain HTTP, leave `COOKIE_SECURE=false`; enable it when serving through HTTPS.
