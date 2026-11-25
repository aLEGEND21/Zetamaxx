# FastAPI + SQLite. Built in CI (.github/workflows/deploy.yml) and shipped to the server.
FROM python:3.15-slim

# uv installs the locked dependencies; the pinned image keeps builds repeatable.
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/srv/venv \
    PATH="/srv/venv/bin:$PATH" \
    DATABASE_PATH=/data/zetamaxx.db

WORKDIR /srv/api

# Dependencies first, so editing app code does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Run as an ordinary user that owns the data folder (the named volume is mounted here).
RUN useradd --system --uid 10001 --home-dir /srv zetamaxx \
    && mkdir -p /data \
    && chown zetamaxx /data
USER zetamaxx
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

# Exactly one worker: one process means one writer, which is what SQLite wants.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
