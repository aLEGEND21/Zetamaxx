import logging
from collections.abc import AsyncIterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event, pool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

API_DIR = Path(__file__).resolve().parents[1]
log = logging.getLogger(__name__)

PRAGMAS = (
    "PRAGMA journal_mode=WAL",  # readers never block the writer
    "PRAGMA busy_timeout=5000",  # wait instead of erroring when briefly locked
    "PRAGMA foreign_keys=ON",  # SQLite ignores foreign keys without this
    "PRAGMA synchronous=NORMAL",  # safe with WAL, much faster
)


def _make_engine():
    path = get_settings().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")

    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        for pragma in PRAGMAS:
            cursor.execute(pragma)
        cursor.close()

    return engine


engine = _make_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _stamped_revision() -> str | None:
    """The migration the database file says it is at, or None for a new file."""
    engine = create_engine(f"sqlite:///{get_settings().database_path}", poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


def run_migrations() -> None:
    """`alembic upgrade head`. Synchronous; call it from a thread at startup.

    If the database is stamped with a migration this code does not have, a newer
    release created it and this is that release being rolled back. Migrations are
    additive only (see CLAUDE.md), so the older code can still use the file: it is
    left as it is instead of failing to start.
    """
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    known = {script.revision for script in ScriptDirectory.from_config(config).walk_revisions()}
    stamped = _stamped_revision()
    if stamped is not None and stamped not in known:
        log.warning("Database is at migration %s, newer than this release; leaving it unchanged", stamped)
        return
    command.upgrade(config, "head")
