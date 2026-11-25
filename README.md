# Zetamaxx

Timed arithmetic drills with progress tracking. You get 120 seconds of addition, subtraction,
multiplication and division; the score is how many you solve.

Groups, friends and custom games are built but currently switched off in the web app. To bring
one back, set its flag to `true` in `web/lib/features.ts`.

- `web/`: Next.js 16 (React 19, Tailwind 4, TanStack Query, Recharts)
- `api/`: FastAPI on Python 3.15 (SQLAlchemy 2.1, Alembic, SQLite)
- Sign-in is handled by [Clerk](https://clerk.com)
- `CLAUDE.md` lists the rules and conventions to follow when changing the code

## Run it locally

You need Node 22 or newer, [uv](https://docs.astral.sh/uv/) (it installs Python 3.15 itself), and a
free Clerk account.

```sh
cp .env.example .env     # then paste in the two Clerk keys (see below)
make install             # uv sync + npm install
make dev                 # API on :8000, web on :3000
```

Open http://localhost:3000. A game starts as soon as the page opens, with or without signing in.

The browser only talks to `localhost:3000`; Next.js forwards `/api/*` to FastAPI. The database is one
file, `data/zetamaxx.db`, created on first start. Open it with `sqlite3 data/zetamaxx.db` or any
SQLite viewer.

### Clerk setup (once)

1. Create an application at https://dashboard.clerk.com. Its **development** instance gives you a
   `pk_test_…` and an `sk_test_…` key. Put them in `.env` as `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and
   `CLERK_SECRET_KEY`.
2. In the dashboard, under **User & authentication**:
   - turn on **Google** and **Email** (verification code or link),
   - turn **Password** off,
   - turn on **Username** and mark it **required**. Profile URLs (`/u/<username>`) and friend
     requests use it. Without it the app still works, but people get a generated name like
     `user_ab12cd34`.

The development instance uses Clerk's shared Google credentials and works on `http://localhost`.

### Sample data

```sh
make seed
```

creates four players (ada, grace, linus, margaret), two groups, friendships and about 60 days of
games, so the charts have something to show. Nobody can sign in as those players, so the script
also makes **your** account their friend and adds it to both groups: sign in once first, then run
`make seed` (run it again any time; it never duplicates anything).

### Commands

| Command | What it does |
|---|---|
| `make dev` | Start API and web together (Ctrl-C stops both) |
| `make test` | Backend tests (pytest) and frontend unit tests (Vitest) |
| `make e2e` | Browser end-to-end test (see below) |
| `make lint` | ruff, ESLint and the TypeScript compiler |
| `make seed` | Add sample data to the dev database |
| `make reset-db` | Delete the dev database, recreate it, and seed it |
| `make backup` | Write a consistent copy of the dev database to `data/backups/` |

## Tests

- **Backend** (`api/tests`): run against a temporary SQLite file with the real migrations and
  pragmas, with the process timezone forced to `Asia/Tokyo` to catch timezone mistakes. Clerk is
  bypassed with fixture users, except for one test that verifies real JWT handling with a locally
  generated key.
- **Frontend** (`web/tests`): the random number generator, problem generator and timer logic.
- **Shared fixture** (`shared/fixtures/problems.json`): the same seeds must produce the same
  problems in Python and TypeScript. Both test suites check it. Regenerate it only when changing the
  generator on purpose: `cd api && uv run python -m app.game.fixture`.
- **End to end** (`web/e2e`): `make e2e` starts its own API and web servers on ports 8210 and 3210
  with a throwaway database, signs in as two test users, plays two real 120-second games, and checks
  the profile. When groups are switched on it also checks the group invite and leaderboard. It
  takes about three minutes.
  - It needs the Clerk development keys in `.env`.
  - On first run it creates two users in the Clerk **development** instance
    (`zetamaxx-e2e-1+clerk_test@example.com` and `…-2…`). Addresses containing `+clerk_test` are
    Clerk test addresses that never receive mail. Set `E2E_USER_1` / `E2E_USER_2` to use others.
  - It uses Playwright's own Chromium (`npx playwright install chromium`), or your installed Chrome
    with `E2E_BROWSER_CHANNEL=chrome make e2e`.

## Deploy

Docker is used in production only; development runs without it (see "Run it locally").

Every push to `main` deploys. GitHub Actions (`.github/workflows/deploy.yml`) runs both test
suites, builds the two Docker images, copies them to the server over SSH and starts them. Nothing
is built on the server, and no image registry is involved.

```
push to main -> tests -> build images -> ship over SSH -> deploy.sh: start, health check, roll back if unhealthy

nginx container --(nginx-proxy network)--> zetamaxx-web (Next.js) --/api/*--> zetamaxx-api (FastAPI, 1 worker) -> volume zetamaxx-data
```

The server is a Linux machine that runs Docker and an nginx container which handles TLS and
domains. This project publishes no ports on the host: nginx reaches the web container by name over
the shared `nginx-proxy` Docker network.

### One-time setup

**1. Clerk production instance.** In the Clerk dashboard create the **production** instance for
your domain (for example `zetamaxx.arnavm.com`) and add the DNS records it asks for. Apply the same
sign-in settings as in development. For Google sign-in, create a Web application OAuth client in
Google Cloud Console, paste Clerk's Authorized Redirect URI into it, enter the client ID and secret
in Clerk, and publish the consent screen to "In production". Development and production have
separate users.

**2. GitHub repository settings** (Settings → Secrets and variables → Actions):

| Kind | Name | Value |
|---|---|---|
| Secret | `DEPLOY_HOST` | The server's address |
| Secret | `DEPLOY_USER` | The SSH user, who must be allowed to run `docker` |
| Secret | `DEPLOY_SSH_KEY` | A private key that user accepts |
| Secret | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk's production publishable key, `pk_live_…` |

The publishable key is not private (it ships to every browser); it is stored with the other
secrets for convenience. It is fixed into the web image when the image is built, so changing it
needs a new deploy.

**3. On the server**, create `/opt/zetamaxx/.env` with the two values that must stay private:

```
CLERK_SECRET_KEY=sk_live_…
ALLOWED_ORIGINS=https://zetamaxx.arnavm.com
```

To keep the production values in one place on your own machine, put them in `.env.production` at
the repo root (gitignored): the two values above plus `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` from
step 2. Nothing in the project reads that file, and it can be copied to the server as it is:
`scp .env.production <user>@<server>:/opt/zetamaxx/.env`.

The deploy refuses to run until this file exists. The `nginx-proxy` Docker network must exist too
(`docker network create nginx-proxy` if this is the first project on the server).

**4. nginx.** Forward the subdomain to the web container and pass the original host and scheme,
which the sign-in redirects rely on:

```nginx
location / {
    proxy_pass http://zetamaxx-web:3000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

### What a deploy does

1. Runs the backend and frontend tests. A failure stops here.
2. Builds `zetamaxx-api` and `zetamaxx-web`, tagged with the commit's short hash.
3. Sends both images to the server and copies `docker-compose.yml` and the scripts to
   `/opt/zetamaxx`.
4. Runs `deploy.sh <tag>` on the server: starts the new containers and requests `/api/health`
   through the web container for up to a minute. That one request passes through the web app, the
   API and the database. The API applies database migrations before it answers.
5. If the check fails, the previous release is started again and the workflow fails.
6. Keeps the current and previous images and deletes older ones.

To go back to the previous release by hand, run this on the server:

```sh
bash /opt/zetamaxx/rollback.sh
```

A rollback changes the code, not the database. The older release keeps running on the database as
the newer one left it, so migrations must only add things (new tables, new columns with defaults).

### Backups

The database is the file `/data/zetamaxx.db` in the `zetamaxx-data` Docker volume, mounted only into
the API container. Deleting the volume deletes the data. Add a nightly cron entry on the server:

```
15 3 * * *  /opt/zetamaxx/backup.sh >> /opt/zetamaxx/backup.log 2>&1
```

The script asks the API container for a consistent snapshot (`python -m app.backup`, SQLite's online
backup API), copies it to `/opt/zetamaxx/backups`, and keeps 14 days. Do not back up by copying the
live `.db` file: recent writes sit in a separate WAL file and a plain copy can be corrupt.

To restore: `docker stop zetamaxx-api`, copy a snapshot over `/data/zetamaxx.db` in the volume,
remove any `zetamaxx.db-wal` and `zetamaxx.db-shm` next to it, then `docker start zetamaxx-api`.

### Not verified yet

The workflow, the compose file and the scripts were checked for syntax and the compose file was
validated, but the images have not been built and no deploy has run. The first push to
`main` after the one-time setup is the real test.

## How a game is kept honest

The server picks the seed and records when the game started. When the game ends, the browser sends
back what was solved and how long each answer took. The server regenerates the problems from the
seed and saves the game only if the problems match, the times fit inside the game's length, the
submission arrives within 30 seconds of when the game should have ended, and the answers are not
impossibly fast. The score is counted by the server; anything the browser claims is ignored. A game
that is restarted or abandoned is never saved.
