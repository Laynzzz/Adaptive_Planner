# Task 1 implementation review

Date: 2026-09-25. Review scope: Task 1 bootstrap against `plan.md` Task 1 and `AGENTS.md`. Reviewed bootstrap commits `a2abcf3` (backend) and `867dc48` (web), plus their current files and the shared domain fixtures. Task 3 was being edited concurrently; unfinished auth/schema changes were not misclassified as finished Task 1 behavior.

## Result

No remaining blocking correctness finding in the reviewed bootstrap increment. One concrete domain-owned fixture defect was found and corrected in the follow-up commit containing this report:

- `tests/fixtures/builders.py`: `snapshot()` initially returned tasks with no deadline, contrary to the plan's explicit two 60-minute tasks due at 17:00. A new test failed with `[None, None]` versus expected deadline slots `[68, 68]`. Both tasks now have the literal same-day timestamp deadline. The same review found missing `load_fixture(name)`; a failing check preceded adding the loader through the real normalization parser. Overrides continue preserving intentionally invalid ownership, time and revision values for independent-validator tests.

Authenticated API wrappers, two signed-in identities, `valid_task_command`, application demo task seeding and their browser journey remain the previously recorded Task 3 dependency. This review does not claim the complete Task 1/R1 gate while those dependent contracts are open.

## Files and behaviors inspected

- `services/planner/src/planner/app.py`, `settings.py`, `cli.py`, `db/session.py`: instance-scoped configuration/engine, database-free liveness, schema-head readiness, redacted readiness failures, CLI failure exit status and engine cleanup.
- `db/migrations/env.py`, initial bootstrap revision, `alembic.ini`: test-injected database URL, one migration lineage and configuration located from source checkout.
- Root/member `pyproject.toml`, `uv.lock`, `.python-version`, root/web npm manifests, `package-lock.json`, `.node-version`: pinned runtime and dependency definitions. Native dependency availability is supported by the original bootstrap evidence, not repeated in this review.
- `compose.yaml`, `tests/conftest.py`, `tests/integration/test_bootstrap.py`: loopback-only development bindings, pinned container digests, per-test random database creation/teardown, unavailable/unmigrated/mismatched/current schema cases and migration visibility without process restart.
- `apps/web/src/App.tsx`, `main.tsx`, readiness tests, Vite configuration, TypeScript configuration, Playwright bootstrap tests: actual readiness validation, visible recovery action, same-origin development proxy and prior real browser evidence.
- `scripts/dev.ps1`, `scripts/verify.ps1`, README, ADR and evidence: checked command exit codes, documented Windows/Linux setup, explicit local-only credentials and honest deferred scope.

## Fresh verification

From the worktree root, Windows local environment, same lockfiles as the implementation:

```powershell
.\.tools\bin\uv.exe run pytest tests/integration/test_bootstrap.py -q
npm.cmd run typecheck
npm.cmd run test --workspace apps/web -- --run src/App.test.tsx
docker compose config --quiet
.\.tools\bin\uv.exe run pytest tests/unit/test_time_rules.py tests/unit/test_task_rules.py tests/unit/test_contracts.py -q
```

Observed results:

- Real PostgreSQL bootstrap integration: **8 passed in 8.76s**, process exit 0.
- TypeScript: exit 0.
- Frontend readiness component: **3 passed**, exit 0.
- Compose configuration: exit 0.
- Domain and corrected shared fixtures: **31 passed in 0.30s**; scoped Ruff check also passed.

The focused component tests replace the network boundary; they are not presented as end-to-end evidence. The separate Task 1 web report already records actual Chromium/bootstrap checks. This review did not rerun Linux CI, cloud deployment, live external integrations or the later authenticated scheduling journey.

## Future packaging consideration

`db/session.py:migration_config()` deliberately discovers `alembic.ini` through the source-tree parent path, and the wheel includes only `src/planner`. This works for the documented editable checkout and its verified local commands. Before Task 18 image/wheel packaging, ensure migrations and their configuration are included at the expected runtime path or make that path explicit. This is a packaging follow-up, not evidence that a deployable artifact has already been produced.
