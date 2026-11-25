# Zetamaxx

A timed arithmetic drill. You get 120 seconds of addition, subtraction, multiplication and division,
and your score is how many you solve. Sign in to save your games and track your progress.

The web app is Next.js (`web/`) and the API is FastAPI with SQLite (`api/`). Sign-in is handled by
[Clerk](https://clerk.com).

Groups, friends and custom games are written but switched off. Each has a flag in
`web/lib/features.ts`.

## Run it locally

You need Node 22 or newer, [uv](https://docs.astral.sh/uv/) and a free Clerk account.

```sh
cp .env.example .env     # paste in your two Clerk development keys
make install
make dev                 # web on :3000, API on :8000
```

Open http://localhost:3000. A game starts as soon as the page loads, signed in or not.

For the keys, create an application at https://dashboard.clerk.com and copy its development
`pk_test_…` and `sk_test_…` keys into `.env`. In the dashboard, turn on Google and Email sign-in,
turn Password off, and make Username required, because profile URLs use it.

The database is one file, `data/zetamaxx.db`, created on first start.

## Commands

| Command | What it does |
|---|---|
| `make dev` | Start the API and the web app together |
| `make test` | Backend tests (pytest) and frontend unit tests (Vitest) |
| `make lint` | ruff, ESLint and the TypeScript compiler |
| `make e2e` | One browser test that plays two full games; takes about three minutes |
| `make seed` | Add sample players and about 60 days of games |
| `make reset-db` | Delete the dev database, recreate it and seed it |
| `make backup` | Write a copy of the dev database to `data/backups/` |

`make e2e` needs the Clerk development keys and creates two test users in that Clerk instance the
first time it runs.

## Deploy

Every push to `main` deploys. GitHub Actions runs the tests, builds two Docker images, copies them
to the server over SSH and starts them. If the new version fails its health check, the previous one
is started again. Docker is only used in production; development runs without it.

One-time setup:

1. In Clerk, create the production instance for your domain and add the DNS records it asks for.
   On Cloudflare, set those records to "DNS only".
2. In the GitHub repository, add four Actions secrets: `DEPLOY_HOST`, `DEPLOY_USER`,
   `DEPLOY_SSH_KEY`, and `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (Clerk's `pk_live_…` key).
3. On the server, create `/opt/zetamaxx/.env` with `CLERK_SECRET_KEY` (the `sk_live_…` key) and
   `ALLOWED_ORIGINS` (the site's address, such as `https://zetamaxx.arnavm.com`).
4. Point your nginx container at `http://zetamaxx-web:3000` over the `nginx-proxy` Docker network,
   passing the `Host` and `X-Forwarded-*` headers. The app publishes no ports of its own.

To go back one release, run `bash /opt/zetamaxx/rollback.sh` on the server. A rollback leaves the
database as it is, so migrations only ever add tables and columns.

The data lives in the `zetamaxx-data` Docker volume. For nightly backups, add this to the server's
crontab. It keeps 14 days of snapshots in `/opt/zetamaxx/backups`.

```
15 3 * * *  sh /opt/zetamaxx/backup.sh >> /opt/zetamaxx/backup.log 2>&1
```

## Working on the code

`CLAUDE.md` lists the rules and conventions to follow when changing the code.
