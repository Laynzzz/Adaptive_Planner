# Adaptive Planner

A personal planner that builds reviewed schedules from tasks, deadlines and available time. The authoritative design is [plan.md](plan.md). The local experimental release includes adaptive workflows, measured SQL/scheduler studies, a rejected ML routing experiment and delivery rehearsal. External release gates remain explicit.

## Current status

The React workspace supports authenticated task entry, reviewed schedules, explicit progress, protected blocks, what-if previews, reviewed natural-language drafts and weekday preferences. ICS export and a persistent calendar simulator exercise recovery without external accounts. PostgreSQL owns revisioned inputs and durable jobs; independent validation checks every proposed schedule. See [execution status](docs/execution-status.md) and [evidence](docs/evidence-index.md).

Live Google, paid AI evaluation, hosted CI and AWS deployment remain **not executed**. Learned routing was not promoted: completion, quality, latency and measurement gates failed. The fixed policy remains the default. Local and simulated results are labeled separately in the in-app **Evidence & limits** view. This is an agent-assisted project using synthetic data, without claims of production adoption or human productivity gains.

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
./scripts/dev.ps1 worker
./scripts/dev.ps1 ai-worker
./scripts/dev.ps1 calendar-worker
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
uv run python -m planner.jobs.worker
uv run python -m planner.ai.worker
uv run python -m planner.calendar.worker
npm run dev
```

## Verification

Local demo sign-in uses `demo-a` / `local-demo-a-only` and `demo-b` / `local-demo-b-only`. These are intentionally public credentials for the loopback-only synthetic identity provider. They are never deployment credentials. After signing in once as each user, `uv run python -m planner.cli seed-demo` populates the synthetic demo tasks without inventing provider subject IDs.

The scheduling worker computes plans; the AI worker processes reviewed extraction drafts; the calendar worker performs synchronization and publication. All three are separate from the API. Local extraction and the calendar simulator require no paid keys. Login, task edits and work-hour changes use server-side sessions and revision checks. A changed-input conflict retains the form draft; refresh the workspace before retrying.

```bash
uv lock --check
uv run ruff check services tests db training benchmarks evals
uv run pytest -q
npm run typecheck
npm run api:check
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Windows convenience: `./scripts/verify.ps1 -Browser`. Real database integration tests create and drop only uniquely named test databases. The database and local OIDC provider must be running. Browser tests require the development database migrated to current head and all three workers running; Playwright starts missing API/web processes automatically. After a new migration is added, apply it and restart the API and workers.

## Learning and evidence

- [Learning guide / 学习指南](docs/teaching-guide.md)
- [Interview preparation](docs/interview-prep.md)
- [Architecture decisions](docs/adr/0001-stack.md)
- [Verification evidence index](docs/evidence-index.md)

Stop local services with `docker compose stop`. This retains the project database volume. No AWS resources have been created and no paid model calls have run. The CPU-only scheduler and small tabular models do not benefit from the4090. Local containers, synthetic databases and ignored benchmark/video artifacts are intentionally retained; see the final release report for inventory.

## Recorded results and recordings

- [SQL measurements](docs/evidence/sql-performance.md): read improvement, write cost and end-to-end regression are all reported.
- [Scheduler measurements](docs/evidence/scheduler-benchmarks.md):1,000 groups,7,000 runs, failures and the old supervision limitation retained.
- [ML experiment](docs/evidence/ml-experiment.md): frozen selection, audited report correction, negative deployment decision.
- [Local release verification](docs/evidence/local-release.md): clean checkout, tests, resources and limits.
- [Product demo](docs/demo-script.md) and [technical walkthrough](docs/technical-walkthrough.md): agent-operated synthetic recordings, not human usability studies.

The200-task maximum is an input boundary, not demonstrated successful scheduling capacity. Large cases frequently returnedUNKNOWN under the short benchmark budgets. Live provider, hosted CI and AWS deployment claims require separate executed evidence.
