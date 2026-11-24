.PHONY: dev api web install test test-api test-web e2e lint seed reset-db backup

# Start the API (:8000) and the web app (:3000) together. Ctrl-C stops both.
dev:
	@trap 'kill 0' INT TERM EXIT; \
	(cd api && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd web && npm run dev) & \
	wait

api:
	cd api && uv run uvicorn app.main:app --reload --port 8000

web:
	cd web && npm run dev

install:
	cd api && uv sync
	cd web && npm install

test: test-api test-web

test-api:
	cd api && uv run pytest -q

test-web:
	cd web && npm test

# End-to-end smoke test (about 3 minutes). Starts its own servers on ports 3210/8210
# with a throwaway database, and needs the Clerk dev keys in .env (see README).
e2e:
	cd web && npx playwright test

lint:
	cd api && uv run ruff check . && uv run ruff format --check .
	cd web && npm run lint && npx tsc --noEmit

# Dev-only sample data: 4 users, 2 groups, friendships, ~60 days of games.
seed:
	cd api && uv run python -m app.seed

# Delete the dev database, then re-run migrations and the seed script.
reset-db:
	rm -f data/zetamaxx.db data/zetamaxx.db-wal data/zetamaxx.db-shm
	cd api && uv run alembic upgrade head
	cd api && uv run python -m app.seed

# Consistent copy of the dev database into data/backups/ (SQLite online backup API).
backup:
	cd api && uv run python -m app.backup
