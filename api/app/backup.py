"""Consistent backup of the live database.

    python -m app.backup            (prod: docker compose exec -T api python -m app.backup)

Uses SQLite's online backup API, which copies a consistent snapshot even while
the app is writing. Never copy the live .db file directly: with WAL, recent
writes live in a separate file and a plain copy can be torn.

Writes <backup dir>/zetamaxx-YYYYMMDD.db (default: a `backups` folder next to
the database) and keeps the newest 14 there.
"""

import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings

KEEP = 14


def backup(source: Path, backup_dir: Path, today: str | None = None) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"no database at {source}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    today = today or datetime.now(UTC).strftime("%Y%m%d")
    target = backup_dir / f"zetamaxx-{today}.db"
    partial = target.with_suffix(".db.partial")
    partial.unlink(missing_ok=True)

    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(partial)
    try:
        src.backup(dst)
        ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != "ok":
            raise RuntimeError(f"backup failed its integrity check: {ok}")
    finally:
        dst.close()
        src.close()
    partial.replace(target)  # only a complete, verified file gets the final name

    for old in sorted(backup_dir.glob("zetamaxx-*.db"), reverse=True)[KEEP:]:
        old.unlink()
    return target


def main() -> None:
    settings = get_settings()
    backup_dir = settings.backup_dir or settings.database_path.parent / "backups"
    try:
        target = backup(settings.database_path, backup_dir)
    except Exception as exc:  # noqa: BLE001 - report any failure to cron with a non-zero exit
        sys.exit(f"backup failed: {exc}")
    print(target)


if __name__ == "__main__":
    main()
