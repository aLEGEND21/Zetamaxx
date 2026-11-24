"""Test setup.

Runs against a fresh temporary SQLite file per test session (migrations applied,
same pragmas as prod), never the dev database. The process timezone is forced to
Asia/Tokyo so any naive-datetime bug shows up as a wrong date.
"""

import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

os.environ["TZ"] = "Asia/Tokyo"
time.tzset()

_tmpdir = tempfile.TemporaryDirectory(prefix="zetamaxx-test-")
os.environ["DATABASE_PATH"] = str(Path(_tmpdir.name) / "test.db")
os.environ["CLERK_SECRET_KEY"] = "sk_test_dummy"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"

import pytest  # noqa: E402
from fastapi import Depends, Request  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.auth import current_user  # noqa: E402
from app.db import SessionLocal, engine, get_session, run_migrations  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, User  # noqa: E402


async def _header_user(request: Request, session=Depends(get_session)):
    """Test stand-in for Clerk: the `X-Test-User` header names the signed-in user."""
    username = request.headers.get("x-test-user")
    if not username:
        return None
    return (await session.execute(select(User).where(User.username == username))).scalar_one()


@pytest.fixture(autouse=True)
def _bypass_clerk():
    app.dependency_overrides[current_user] = _header_user
    yield
    app.dependency_overrides.pop(current_user, None)


def auth(user: User | str) -> dict[str, str]:
    """Request headers that sign `user` in."""
    return {"X-Test-User": user if isinstance(user, str) else user.username}


@pytest.fixture
def make_user():
    async def _make(username: str, timezone: str = "America/New_York", **fields) -> User:
        async with SessionLocal() as session:
            fields.setdefault("timezone_set", True)
            user = User(clerk_user_id=f"clerk_{username}", username=username, timezone=timezone, **fields)
            session.add(user)
            await session.commit()
            return user

    return _make


@pytest.fixture
def clock():
    """A frozen clock the test moves by hand. Starts on a plain Monday afternoon (UTC)."""
    import time_machine

    with time_machine.travel(datetime(2026, 6, 15, 16, 0, tzinfo=UTC), tick=False) as traveller:
        yield traveller


@pytest.fixture(scope="session", autouse=True)
def _migrated_db():
    run_migrations()
    yield
    _tmpdir.cleanup()


@pytest.fixture(autouse=True)
async def _clean_tables(_migrated_db):
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"X-Requested-With": "fetch"}) as c:
        yield c
