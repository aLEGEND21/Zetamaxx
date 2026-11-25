# Zetamaxx

Timed arithmetic drill (120 seconds, score = problems solved) with saved history, personal stats,
groups with leaderboards, and friends. `README.md` covers setup, Clerk configuration and deployment;
this file covers what to know before changing the code.

## Commands

| Command | What it does |
|---|---|
| `make dev` | API on :8000 and web on :3000 together |
| `make test` | pytest (api) and Vitest (web) |
| `make lint` | ruff check + format check, ESLint, `tsc --noEmit` |
| `make e2e` | Playwright test, about 3 minutes; starts its own servers on :3210 / :8210 |
| `make seed` / `make reset-db` | Sample data / wipe and recreate the dev database |

Single test: `cd api && uv run pytest tests/test_games.py -k name` or `cd web && npx vitest run tests/generator.test.ts`.

Run `make lint` and `make test` before calling a change done. CI runs both test suites on every
push to `main`, and a failure blocks the deploy.

## Layout

- `api/`: FastAPI on Python 3.15, managed with `uv`. SQLAlchemy 2.1 async over SQLite, Alembic.
  - `app/routers/`: `auth` (`/api/me`), `games`, `stats`, `groups`, `friends`
  - `app/services/`: `validation` (game submission), `stats`, `visibility`, `localtime`, `clerk`
  - `app/game/`: `prng`, `generator`, `settings`, `fixture` (regenerates the shared fixture)
  - `app/auth.py`: Clerk JWT verification and the `optional_user` / `require_user` dependencies
- `web/`: Next.js 16, React 19, Tailwind 4, TanStack Query, Recharts, Clerk.
  - `app/`: routes. `components/views/`: one client view per page. `components/charts/`: charts.
  - `lib/`: `prng`, `generator`, `engine`, `timer` (game logic), `api` (fetch wrapper), `pending`
    (queued saves and guest claims), `dates`, `types` (API response shapes)
- `shared/fixtures/problems.json`: the generator contract between the two apps (see below).
- `.github/workflows/deploy.yml`, `docker-compose.yml`, `scripts/{deploy,rollback,backup}.sh`:
  the deploy pipeline. The three scripts run on the server, from `/opt/zetamaxx`.
- `data/zetamaxx.db`: dev database, gitignored. `.env` at the repo root is read by both apps.

The browser only talks to the web app; `next.config.ts` rewrites `/api/*` to FastAPI, so there is
one origin and no CORS.

## Rules that must hold

**The problem generator is duplicated on purpose.** `web/lib/{prng,generator}.ts` and
`api/app/game/{prng,generator}.py` must produce identical sequences from the same seed, because the
server regenerates each game to validate it. Both test suites check `shared/fixtures/problems.json`.
If they disagree, fix that before anything else. Regenerate the fixture only when changing the
generator deliberately: `cd api && uv run python -m app.game.fixture`.

**Game validation** (`api/app/services/validation.py`):
- The server issues the seed and start time; the score is counted by the server, never taken from
  the client.
- A game is saved only if it arrives within 30 seconds of when it should have ended. There is no
  late path. For that reason the client uses a prefetched start only if it is under 20 seconds old.
- Restarted or abandoned games leave no trace. A rejected submission deletes its start row, and
  unused starts are pruned after 16 minutes.
- A game with no answers counts as abandoned: the client does not send it and the server rejects it.
  This matters because opening `/` starts a game, so an idle visit must not record a score of 0.
- Answers under 150 ms: more than 10% rejects the game; fewer saves it with `games.flagged = true`.
  Nothing reads that flag yet.
- Guests' games are validated and held on the `game_starts` row, then claimed after sign-in, up to
  15 minutes after the game started.
- No network calls during play.

**Time and dates:**
- Timestamps are UTC, stored through the `UTCDateTime` type, always timezone-aware. Never call
  `.astimezone()` on a naive datetime, and never use `date.today()` or the server's date.
- Each game stores the player's local date, hour and offset at the moment it finished. Per-day stats
  group by that stored `local_date`; no timezone math at read time. "Today" for a streak is today in
  the profile owner's timezone.
- Backend tests run with `TZ=Asia/Tokyo` to catch mistakes here.
- Frontend: never pass a `YYYY-MM-DD` string to `new Date()` (it shifts a day in US timezones). Use
  the day-number helpers in `web/lib/dates.ts`.

**Who can see what** (`api/app/services/visibility.py`): yourself, accepted friends, and anyone who
shares a group with you see everything. Everyone else gets username and personal best only.

**Database:**
- SQLite with one writer: uvicorn always runs with exactly one worker, in dev and in Docker.
- Keep SQL portable (SQLAlchemy only, nothing SQLite-specific) so a move to Postgres stays possible.
- Schema changes go through a new Alembic migration (batch mode). Migrations run on API startup.
- **Migrations are additive only**: new tables, new nullable or defaulted columns, indexes. No drops
  or renames. A failed deploy restarts the previous release on the already-migrated database, and
  that older code must still work with it. (`run_migrations` leaves a database alone when it is
  stamped with a migration the running code does not know.)

**API conventions:**
- Errors are `{"error": {"code", "message"}}`.
- Mutating requests need the header `X-Requested-With: fetch` (`web/lib/api.ts` adds it).
- Response shapes are mirrored by hand in `web/lib/types.ts`; update both sides together.

**Secrets:** the Clerk keys live only in `.env`. Never commit it, and never print its contents.

**Deployment:** every push to `main` deploys (`.github/workflows/deploy.yml`): tests, image builds
in CI, images shipped over SSH, then `scripts/deploy.sh` on the server starts them, health-checks
`/api/health` through the web container and restarts the previous release if that fails.
- Docker is for production only; development never uses it. `docker-compose.yml` is the production
  stack and publishes no host ports. An nginx container outside this
  project handles TLS and reaches `zetamaxx-web` over the external `nginx-proxy` network. Never
  bind 80 or 443.
- Only the `zetamaxx-api` container mounts the data volume.
- Secrets live in `/opt/zetamaxx/.env` on the server. The Clerk publishable key is a GitHub
  repository secret, fixed into the web image at build time. `.env.production` at the repo
  root (gitignored) is the owner's local copy of those production values; no code reads it, and
  like `.env` it must never be printed or committed.

## Next.js 16 notes

- Read the relevant guide in `web/node_modules/next/dist/docs/` before using a Next API; this
  version differs from older ones (`web/AGENTS.md`).
- The middleware file is `web/proxy.ts`. It redirects signed-out visitors away from `/friends` and
  `/groups`. Do not move that check into a layout: it breaks Next's development validation.
  `/settings` holds only the custom-mode form: public (guests can use it), and 404 while
  `CUSTOM_MODE` is off. There is no general settings page: the timezone picker is on the player's
  own profile, and account details are in Clerk's "Manage account" window under the avatar.
- Cache Components is on. A route with a dynamic URL part is a server `page.tsx` that wraps a client
  view in `<Suspense>`; the view reads the parameter with `useParams()`.
- After adding or removing a route, run `npx next typegen` in `web/` if `tsc` complains about
  `.next/types`.

## Design

Light theme only, near-monochrome, one blue accent. The colours, fonts, 12px card radius and 960px
content width are CSS variables in `web/app/globals.css`; use those rather than new values. Numbers
that change use the mono font with tabular digits. Borders instead of shadows, motion under 180 ms
on the one easing curve (`--ease`). Chart colours and line widths are in
`web/components/charts/theme.ts`.

`--accent` is for graphics (the logo, chart lines, the focus ring). Blue text, and any blue fill
under white text, uses the darker `--accent-ink` (`text-accent-ink`, `bg-accent-ink`), which meets
4.5:1 contrast. Spacing and control heights sit on a 4px grid. Keyboard shortcuts are shown as
keycaps with `<kbd>`.

The game screen must stay instant: state in refs, one render tick, the answer advances on the
keystroke that completes it with no Enter key. There is no start screen: opening `/` starts a game
(a background tab waits until it is visible), Escape or Restart starts a fresh one at once, and
Enter on the results plays again.

## Scope

- **Switched off in the UI:** `web/lib/features.ts` has `SOCIAL` (friends, groups, invite links) and
  `CUSTOM_MODE` (custom games), both currently `false`. The code and the API for them are intact;
  the flags hide the nav links, controls and pages (which return 404). Keep new UI for these
  features behind the same flags.
- Ask before adding a feature. Prefer simple, readable code; no state library beyond TanStack Query.
- Left out on purpose: real-time races, a daily challenge, a weak-spot drill mode, public profiles
  and a global leaderboard, Clerk webhooks, dark mode, native mobile apps.
- The schema has an `admin` group role, but no endpoint assigns it yet.
