import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy import text

from app.db import SessionLocal, run_migrations
from app.errors import error_response, register_error_handlers
from app.routers import auth, friends, games, groups, stats

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Bring the database up to date before serving anything.
    await asyncio.to_thread(run_migrations)
    yield


app = FastAPI(title="Zetamaxx API", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
register_error_handlers(app)
app.include_router(auth.router)
app.include_router(games.router)
app.include_router(stats.router)
app.include_router(groups.router)
app.include_router(friends.router)


@app.middleware("http")
async def require_fetch_header(request: Request, call_next):
    """Cheap CSRF protection: a cross-site form post cannot set a custom header."""
    if request.method in MUTATING_METHODS and request.headers.get("x-requested-with") != "fetch":
        return error_response(403, "csrf", "Missing X-Requested-With: fetch header")
    return await call_next(request)


@app.get("/api/health")
async def health():
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
