# Task 1 web foundation evidence

Date: 2026-09-25. Local Windows, Node 22.20.0/npm 10.9.3, Vite 8.3.1, React 19.3.0, Vitest 5.0.2, Playwright 1.63.0. Dependency graph: root package-lock.json.

- `npm run test --workspace apps/web -- --run`: 3 tests initially failed against an empty component. [Red output](raw/task-1-web-red.txt).
- First implementation returned no data from TanStack Query; 2 tests correctly failed. [Intermediate failure](raw/task-1-web-intermediate-failure.txt). Returning the validated success value fixed the query contract without weakening tests.
- Same test command: 3 passed. [Green output](raw/task-1-web-green.txt).
- `npm run build`: TypeScript check and production Vite build passed. [Build output](raw/task-1-web-build.txt).
- `npm run test:e2e -- tests/e2e/bootstrap.spec.ts`: 2 passed against actual local FastAPI/PostgreSQL through Vite proxy. [Browser output](raw/task-1-browser.txt).
- Inspected [desktop](raw/bootstrap-desktop.png) and [390px mobile](raw/bootstrap-mobile.png) screenshots. No horizontal overflow; retry can be activated by keyboard.

The browser failure test intercepts readiness with 503, then removes interception and retries against the actual service. This proves web recovery handling, not an external calendar integration. The initial shell contains no invented task data or scheduler success claims. In-app browser tooling failed before connection (kernel-assets path error); repository Playwright tests supplied real Chromium verification instead.

Bootstrap frontend is verified; R1 auth/task/plan journey remains pending.
