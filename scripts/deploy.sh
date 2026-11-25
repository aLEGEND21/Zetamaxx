#!/usr/bin/env bash
# Runs ON the VPS. Brings the compose stack up on the given image tag,
# health-checks the full chain (web proxy -> api -> database), and
# automatically falls back to the previous release if it won't serve.
#
# Usage: deploy.sh <image-tag>
set -euo pipefail

TAG="${1:?usage: deploy.sh <image-tag>}"
STATE_DIR="/opt/zetamaxx"

cd "$STATE_DIR"

# Without the Clerk keys the site would start but nobody could sign in, so stop
# before touching the running release.
if [ ! -f .env ]; then
  echo "Missing $STATE_DIR/.env (CLERK_SECRET_KEY, ALLOWED_ORIGINS). Nothing was changed." >&2
  exit 1
fi

CURRENT="$(cat current 2>/dev/null || true)"

start_stack() {
  TAG="$1" docker compose up -d --remove-orphans
}

healthy() {
  # /api/health on the web container is forwarded to the api, which also runs
  # a query, so one probe verifies both containers, the network between them,
  # and the database. The api applies migrations before it answers.
  for _ in $(seq 1 60); do
    if docker exec zetamaxx-web wget -qO /dev/null http://127.0.0.1:3000/api/health 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

echo "Deploying zetamaxx:$TAG"
start_stack "$TAG"

if ! healthy; then
  echo "Health check failed for zetamaxx:$TAG" >&2
  if [ -n "$CURRENT" ]; then
    echo "Restoring zetamaxx:$CURRENT" >&2
    start_stack "$CURRENT"
  fi
  exit 1
fi

if [ -n "$CURRENT" ] && [ "$CURRENT" != "$TAG" ]; then
  echo "$CURRENT" > previous
fi
echo "$TAG" > current

# Prune all release images except current and previous.
PREVIOUS="$(cat previous 2>/dev/null || echo none)"
for IMAGE in zetamaxx-api zetamaxx-web; do
  docker images "$IMAGE" --format '{{.Tag}}' |
    grep -v -e "^$TAG$" -e "^$PREVIOUS$" |
    xargs -r -I{} docker rmi "$IMAGE:{}" > /dev/null 2>&1 || true
done

echo "Deployed zetamaxx:$TAG"
