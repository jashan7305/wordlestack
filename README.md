# WordleStack

WordleStack is a self-hosted daily Wordle competition. Play the daily puzzle, compare results with friends, and compete in private Leagues.

## Setup

1. Install Docker and Docker Compose.
2. Copy `.env.example` to `.env`:

   ```sh
   cp .env.example .env
   ```

3. Edit `.env`. Set a strong, unique value for `DB_PASSWORD`, `SECRET_KEY`, and `ADMIN_PASSWORD`. Set `PUBLIC_URL` to the address where WordleStack will be available. For local use, the defaults are suitable after replacing the placeholder secrets.
4. Start the application from the repository directory:

   ```sh
   docker compose up -d --build
   ```

5. Open <http://localhost:8002> (or the address configured for your deployment) and sign in with the administrator username and password from `.env`.

The administrator account is created on first startup. Changing its credentials in `.env` later does not change the existing account. Your data is kept in a Docker volume when you stop the application with `docker compose down`.

## Features

- **Daily Wordle:** Play the official daily five-letter puzzle in the familiar six-guess format. Each person gets one game per puzzle date.
- **Leagues:** Administrators can create private Leagues, manage members, and invite people with expiring links. A player's daily result counts in every League they belong to.
- **Leaderboards:** Compare daily League results, overall League standings, and global points.
- **Statistics:** Review games played, wins, streaks, guess distribution, points, and past results.
- **Administration:** Manage user accounts and League membership from the admin pages.

## Managing the deployment

```sh
# View service status and logs
docker compose ps
docker compose logs -f app

# Stop the application while keeping its data
docker compose down

# Start it again
docker compose up -d
```

To permanently remove the database and all saved data, run `docker compose down -v`.
