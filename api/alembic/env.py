"""Alembic environment.

Migrations run on a plain synchronous sqlite3 connection (simpler than driving
the async engine, and safe to call from the API's startup thread). Batch mode is
on because SQLite cannot ALTER most columns in place.
"""

from alembic import context
from sqlalchemy import create_engine, event, pool

from app.config import get_settings
from app.models import Base

target_metadata = Base.metadata


def _url() -> str:
    path = get_settings().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)

    # By default Python's sqlite3 commits DDL immediately, so a process killed
    # between "CREATE TABLE" and recording the revision leaves the database
    # half-migrated. Taking over transaction control (SQLAlchemy's documented
    # pysqlite recipe) makes each upgrade atomic: it either fully applies or
    # rolls back.
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _record):
        dbapi_connection.isolation_level = None
        dbapi_connection.execute("PRAGMA journal_mode=WAL")
        dbapi_connection.execute("PRAGMA busy_timeout=5000")

    @event.listens_for(engine, "begin")
    def _on_begin(connection):
        connection.exec_driver_sql("BEGIN IMMEDIATE")

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            transactional_ddl=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
