# Task 1 backend/bootstrap evidence

Date: 2026-09-25. Local Windows x64, Docker Desktop Linux containers. Scope: backend bootstrap only, not an R1 release. Revision is the commit introducing this report; commands ran against its staged implementation. Commands below run from repository root. This machine used `.\.tools\bin\uv.exe` for `uv` (uv 0.12.19).

## What is implemented

- Root uv workspace installs the editable `planner` package and test tools; all direct dependencies are pinned and the complete resolution is in `uv.lock`.
- FastAPI factory owns configuration/engine per instance. `/health/live` does not access PostgreSQL. `/health/ready` returns 503 for unavailable, empty, or mismatched-schema databases and 200 only when database Alembic heads equal checked-in migration heads. Database exceptions and credentials are not returned.
- Alembic initial revision creates the migration lineage only. No user/domain table or identity is represented as implemented yet.
- Each database test creates a random `planner_test_<uuid>` database on the local test server, migrates it where needed, and drops that exact database in teardown. The application database is never reused as test data. Override only with a dedicated test server through `PLANNER_TEST_ADMIN_URL`.
- CLI `serve` runs loopback HTTP and `check-ready` exits 0/1 based on actual readiness. `seed-demo` deliberately exits with an explicit unsupported message until Task 3 supplies identity/task storage.
- Compose binds PostgreSQL to 127.0.0.1:25432 and Keycloak to 127.0.0.1:28080 (port overrides are supported). Container images have exact release tags and immutable manifest digests. Keycloak imports two synthetic users and an authorization-code/PKCE client. Listed passwords are intentionally local fixture values, never production credentials.

## Test-first record

1. Empty app factory, configured test harness, no routes:
   `uv run pytest tests/integration/test_bootstrap.py -q`
   **4 failed**: expected live 200, unavailable 503, unmigrated 503 and migrated 200; actual response was 404 for each. Real PostgreSQL fixture creation/migration/teardown succeeded, so the failures established missing app behavior.
2. Implemented health routes and schema-head readiness:
   same command: **4 passed in 3.85s**.
3. Added CLI readiness contracts with an empty command dispatcher:
   same command: **2 failed, 6 passed in 4.14s**. Unavailable database incorrectly exited 0; migrated database produced no `ready` output.
4. Implemented CLI dispatch and readiness exit status:
   same command: **8 passed in 8.74s**. Added regression coverage rejects an unknown schema revision and observes migration without API restart.
5. Final verification after formatting and exact pins:
   `uv sync --frozen --all-extras`: **Checked 55 packages**.
   `uv run pytest tests/integration/test_bootstrap.py -q`: **8 passed in 8.53s**, no warnings.
   `uv run ruff check services/planner/src/planner/app.py services/planner/src/planner/settings.py services/planner/src/planner/cli.py services/planner/src/planner/db tests/conftest.py tests/integration/test_bootstrap.py db/migrations`: **All checks passed!**

## Additional executed checks

- `docker compose up -d postgres oidc`: both services started; PostgreSQL healthy.
- `docker compose config --quiet`: exit 0.
- `uv run alembic upgrade head`, then `uv run python -m planner.cli check-ready`: exit 0, `ready`.
- Real CLI HTTP process on loopback port 28001: `GET /health/ready` returned 200 and `{"status":"ready"}`. Process terminated after smoke check.
- GET `http://127.0.0.1:28080/realms/adaptive-planner/.well-known/openid-configuration` returned issuer `http://127.0.0.1:28080/realms/adaptive-planner`.
- OR-Tools minimal Boolean model returned OPTIMAL with x=1; scikit-learn DummyClassifier fit/predict returned the expected majority class. These establish imports/native wheel interoperability only, not scheduling correctness or ML quality.
- `docker compose exec -T postgres psql -U planner -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'planner_test_%';"`: empty output after tests, no test databases remained.

## Versions, compatibility, and setup caveats

Python 3.12.14; FastAPI 0.135.1; Starlette 0.52.1; AnyIO 4.12.1; Pydantic 2.13.5; SQLAlchemy 2.0.48; Alembic 1.20.0; psycopg 3.3.6; OR-Tools 9.15.6755; scikit-learn 1.9.1; Authlib 1.8.0; pytest 9.1.1; Hypothesis 6.168.1; Ruff 0.16.9. Additional versions are authoritative in pyproject/lock files.

Initial unconstrained resolution selected Starlette 1.7.0, whose HTTPX-based TestClient emitted a deprecation warning; Starlette 0.52.1 with current AnyIO also emitted a deprecated alias warning. Pinning the compatible FastAPI/Starlette/AnyIO combination above eliminated both warnings; they were not filtered/suppressed. Initial Ruff check found import ordering and long lines; fixes were applied and the final check passed.

`uv python install 3.12.14` downloaded a working interpreter but reported a Windows minor-version-link error. The exact interpreter passed `--version` and `uv sync` discovered it via the exact `.python-version`; no global PATH change or link deletion was needed. This host issue is recorded rather than presented as a successful installation command.

Sources consulted: [uv workspace installation](https://docs.astral.sh/uv/concepts/projects/workspaces/), [Keycloak container realm import](https://www.keycloak.org/server/containers), [PostgreSQL support policy](https://www.postgresql.org/support/versioning/). Registry pulls and installed native smoke tests establish availability for the versions actually pinned. No AWS/RDS compatibility or cloud execution is claimed.

## Deferred contracts and retained resources

Task 1 is partial until dependent domain/authentication work supplies production-parser builders and authenticated API wrappers. Real application OIDC callback, server-side sessions, CSRF, two authenticated API clients, domain schema and demo task seeding belong to Task 3. The provider fixture is not an authentication bypass and provider discovery is not proof of browser sign-in. The domain agent owns the fake clock, typed builders and fixture loader; their status is documented separately.

PostgreSQL and Keycloak local containers, their Compose network, and the application PostgreSQL volume are intentionally retained for development. Stop with `docker compose stop`; remove containers/network with `docker compose down`. No paid resources were created. Do not use `down -v` unless deletion of local demo database contents is intended.
