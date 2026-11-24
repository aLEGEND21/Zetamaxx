from collections.abc import AsyncIterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

API_DIR = Path(__file__).resolve().parents[1]

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


def run_migrations() -> None:
    """`alembic upgrade head`. Synchronous; call it from a thread at startup."""
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    command.upgrade(config, "head")
