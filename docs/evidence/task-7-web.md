# Task 7 web journey (in progress)

Date: 2026-09-25. Local Windows, Node22.20.0, actual Chromium through Playwright1.63.0, React19.3.0. Root package lock records all dependencies.

## Executed

- 10 component tests passed after adding authenticated workspace, task fields, availability, fixed commitments/dependencies, proposal inspection and explicit activation. Initial red outputs for each slice are under `raw/`.
- Real OIDC two-user journey: `npm run test:e2e -- tests/e2e/tasks.spec.ts` passed. User A created a task; a separately authenticated B could not see it. [Output](raw/task-browser-green.txt).
- Full browser journey: `npm run test:e2e -- tests/e2e/planner.spec.ts` passed against API, PostgreSQL, Keycloak and the separate worker. Created two tasks, set tomorrow's work window, generated, inspected and explicitly activated. [Output](raw/planner-browser-green.txt), [proposal](raw/planner-proposal.png), [active](raw/planner-active.png), [mobile](raw/planner-mobile.png).
- Earlier browser attempts failed because a new migration had not yet been loaded by the running API; the readiness gate correctly blocked use. Another failed because the test matched both visible task text and hidden dependency options; the selector now scopes the task list. These were harness/development-state failures, not red proofs of missing scheduling behavior; raw outputs remain available.
- OpenAPI JSON and TypeScript interfaces are generated from the app with `npm run api:generate`; `npm run api:check` and the Python contract test compare against current routes. UI consumes generated types for task, identity, availability, proposal and job responses.

## Review regressions

- Availability draft used a newer identity revision with an older window snapshot. [Regression red](raw/availability-race-red.txt), [green](raw/availability-race-green.txt). Replacement now uses the availability snapshot's revision; a 409 refreshes data while retaining the draft. Backend also needs a coherent data/revision snapshot (tracked in its report).
- Failed jobs expose diagnostic candidates even when no proposal is created. UI originally ignored those candidates. [Regression red](raw/failed-plan-diagnostics-red.txt), [green](raw/failed-plan-diagnostics-green.txt). It now renders the failed candidate's status and constraints while withholding activation.

## Limits

R1 final gate is pending whole-suite review and clean setup reproduction. This journey establishes local synthetic behavior only. It does not establish hosted deployment, a live AI provider or Google calendar synchronization. UI uses UTC identity defaults; timezone-change preview remains to be connected. No drag controls are required: all implemented operations use labeled forms and keyboard-operable buttons.
