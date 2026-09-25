# Adaptive Planner

A personal planner that builds reviewed schedules from tasks, deadlines and available time. The authoritative design is [plan.md](plan.md). Implementation is in progress; no release gate is claimed complete yet.

## Current status

The initial FastAPI application, PostgreSQL migration harness and React workspace run locally. Health checks distinguish a live process from a database ready to serve requests. Domain rules and the R1 scheduling journey are being implemented. See [execution status](docs/execution-status.md) and [evidence](docs/evidence-index.md).

## Requirements

- Node 22.20.0 / npm 10.9.3 (`.node-version`, `package.json`).
- uv (tested 0.12.19), which provisions the pinned Python 3.12 interpreter.
- Running Docker Engine / Docker Desktop with Linux containers.
- No paid provider keys are required for local development.

Dependencies are locked in `uv.lock` and `package-lock.json`. The local Compose credentials are public synthetic development fixtures, bound to loopback; do not use this Compose configuration as a public deployment.

## Windows setup

From the repository root with uv on PATH:

```powershell
./scripts/dev.ps1 setup
# Separate terminals:
./scripts/dev.ps1 api
./scripts/dev.ps1 web
```

Open <http://127.0.0.1:5173>. The API is at <http://127.0.0.1:8000/docs>. PostgreSQL binds port 25432 and the local OIDC provider binds 28080. Use the documented host consistently for login cookies.

This development worktree also contains an ignored `.tools/bin/uv.exe`; scripts prefer it if present. A fresh checkout requires uv installed separately.

## Linux / CI setup

```bash
uv sync --frozen --all-extras
npm ci
docker compose up -d --wait postgres oidc
uv run alembic upgrade head
# Separate terminals:
uv run python -m planner.cli serve
npm run dev
```

## Verification

```bash
uv run ruff check services tests db
uv run pytest -q
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Windows convenience: `./scripts/verify.ps1 -Browser`. Real database integration tests create and drop only uniquely named test databases. The database must be running. Browser tests require the development database migrated to current head; Playwright starts missing API/web processes automatically.

## Learning and evidence

- [Learning guide / 学习指南](docs/teaching-guide.md)
- [Interview preparation](docs/interview-prep.md)
- [Architecture decisions](docs/adr/0001-stack.md)
- [Verification evidence index](docs/evidence-index.md)

Stop local services with `docker compose stop`. This retains the project database volume. No cloud resources have been created, no paid calls have run, and no GPU workload is needed for the current increment.
