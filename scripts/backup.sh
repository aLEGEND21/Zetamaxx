#!/bin/sh
# Runs ON the VPS, nightly from cron (each deploy copies this file to /opt/zetamaxx):
#
#   15 3 * * *  /opt/zetamaxx/backup.sh >> /opt/zetamaxx/backup.log 2>&1
#
# 1. Asks the api container for a consistent snapshot (SQLite online backup API),
#    written to /data/backups/zetamaxx-YYYYMMDD.db inside the data volume.
# 2. Copies that snapshot out to the host and keeps 14 days of them.
#
# Never copy the live .db file instead: with WAL its newest writes sit in a
# separate file, and a plain copy can be torn.
set -eu

DEST="${BACKUP_DEST:-/opt/zetamaxx/backups}"
KEEP_DAYS=14

snapshot=$(docker exec zetamaxx-api python -m app.backup | tail -n 1)
case "$snapshot" in
  /data/backups/zetamaxx-*.db) ;;
  *) echo "backup failed: unexpected output '$snapshot'" >&2; exit 1 ;;
esac

mkdir -p "$DEST"
docker cp "zetamaxx-api:$snapshot" "$DEST/"
find "$DEST" -name 'zetamaxx-*.db' -type f -mtime +"$KEEP_DAYS" -delete
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) saved $DEST/$(basename "$snapshot")"
