from sqlalchemy import text

from app.db import engine


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok"}


async def test_pragmas_applied():
    async with engine.connect() as conn:
        assert (await conn.execute(text("PRAGMA journal_mode"))).scalar() == "wal"
        assert (await conn.execute(text("PRAGMA foreign_keys"))).scalar() == 1
        assert (await conn.execute(text("PRAGMA busy_timeout"))).scalar() == 5000
        assert (await conn.execute(text("PRAGMA synchronous"))).scalar() == 1  # NORMAL


async def test_mutations_need_fetch_header(client):
    r = await client.post("/api/nothing", headers={"X-Requested-With": ""})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "csrf"


async def test_unknown_route_uses_error_shape(client):
    r = await client.get("/api/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
