# syntax=docker/dockerfile:1.7
FROM node:22.20.0-bookworm-slim@sha256:b21fe589dfbe5cc39365d0544b9be3f1f33f55f3c86c87a76ff65a02f8f5848e AS web
WORKDIR /build
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
RUN npm ci --ignore-scripts
COPY apps/web apps/web
COPY docs/evidence docs/evidence
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 AS uv
FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS python-build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY services/planner services/planner
RUN uv sync --frozen --no-dev

FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS runtime
ARG REVISION=uncommitted-local
LABEL org.opencontainers.image.title="Adaptive Planner" org.opencontainers.image.revision=$REVISION
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PLANNER_STATIC_DIST_PATH=/app/web
WORKDIR /app
RUN groupadd --gid 10001 planner && useradd --uid 10001 --gid 10001 --no-create-home planner
COPY --from=python-build /app/.venv /app/.venv
COPY services/planner services/planner
COPY db db
COPY alembic.ini ./
COPY --from=web /build/apps/web/dist /app/web
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=4s --start-period=30s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"]
CMD ["python", "-m", "planner.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
