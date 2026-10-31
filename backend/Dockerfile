# One Dockerfile, two targets:
#   dev  -> docker compose (Flask debug server, includes pytest/ruff, code mounted from your Mac)
#   prod -> Cloud Run (gunicorn, no dev tools). It's the last stage, so it's the default build.

FROM python:3.13-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /bin/uv
# The virtualenv lives in /opt/venv, not /app: compose mounts your code over /app and would
# otherwise hide the installed packages.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PORT=8080
WORKDIR /app
# Copy only the dependency files first so Docker can cache this slow layer between code edits.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM base AS dev
RUN uv sync --frozen
COPY . .
USER 1000
CMD ["flask", "--app", "app:create_app", "run", "--debug", "--host", "0.0.0.0", "--port", "8080"]

FROM base AS prod
COPY . .
# Don't run as root inside the container.
USER 1000
# Cloud Run tells us which port to listen on via $PORT. `exec` makes gunicorn PID 1 so it
# receives Cloud Run's shutdown signal directly.
CMD exec gunicorn --bind ":$PORT" --workers 2 --threads 4 --timeout 120 "app:create_app()"
