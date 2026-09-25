# ADR 0001: Reproducible modular application

Date: 2026-09-25. Status: implementing the approved plan.

The plan pins Python/FastAPI, PostgreSQL, OR-Tools and React/TypeScript. Keep one backend package and separate API/worker processes rather than introducing service-to-service contracts before they are needed.

## Local decisions

- Root uv workspace installs the `planner` member as an editable dependency; tests run from the root. This follows [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/).
- Use Python 3.12 in a managed project virtual environment instead of changing the user's Python 3.10 installation.
- Node 22.20.0 with npm 10.9.3 is available locally. Vite 8.3.1 declares Node `^20.19.0 || >=22.12.0`, which this runtime satisfies; see [Vite guide](https://vite.dev/guide/). Exact direct npm dependencies and the resolved graph are committed.
- Choose PostgreSQL major 17 for local development; cloud region/version availability must be checked before deployment. See [PostgreSQL support policy](https://www.postgresql.org/support/versioning/). Successful local tests do not establish RDS deployment compatibility.
- Test web error/retry behavior by replacing only the network boundary. Use real PostgreSQL for readiness/schema tests, following [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/).

## Interface design

Use a cool slate work surface (#e8edf4), white writing area (#ffffff), ink text (#24344b), blue actions (#365dc9), muted text (#607087), and restrained green confirmation (#27654b). Use system humanist sans typography (Segoe UI) for speed and legibility. A persistent narrow navigation rail and a large agenda surface emphasize planning; avoid decorative metrics or invented task data. Content is left aligned. Small screens stack the navigation and main content. This is an application work surface, not a marketing landing page.

## Consequences

Local installation requires Docker for integration dependencies. Lockfiles preserve resolutions but do not substitute for running compatibility checks. Initial web shell must not imply scheduling is available before its actual journey exists.
