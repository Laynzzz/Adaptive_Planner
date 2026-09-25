# R2 browser and interface evidence

Executed 2026-09-25 on Windows, Node 22.20, Chromium through Playwright 1.63,
local PostgreSQL and real Keycloak OIDC. Starting revision `7bb57b9` plus the
subsequent R2 working changes; final implementation is recorded in local commits.
Accounts and tasks are synthetic. Google and paid AI were not called.

Commands and observed results:

| Command | Result |
| --- | --- |
| `npm test` | 19 tests passed in 2.46 seconds |
| `npm run typecheck` | Passed |
| `npm run build` | Passed; main JS 302.28 kB, gzip 90.43 kB |
| `npm run test:e2e -- tests/e2e/weekday-rules.spec.ts tests/e2e/interpretation.spec.ts tests/e2e/adaptation.spec.ts tests/e2e/calendar.spec.ts` | 4 passed in 23.0 seconds |

The browser run restarted all three workers against finalized migrations through
0013. It verified actual HTTP/database persistence, queue processing and React UI:

- A zero-minute work log preserves an explicit remaining estimate; a locked block
  persists; what-if preview leaves availability and the active plan unchanged;
  applying inputs still does not activate a proposal automatically.
- Local extraction creates a reviewable draft. Confirmation and manual resolution
  are required before task creation. An injected HTTP 503 preserves source text
  and the manual task form.
- A rule-only extraction of “I dislike Sundays” requires confirmation, appears in
  weekly preferences, survives reload, and can be explicitly removed.
- ICS downloads from the active plan. Calendar connection requires dedicated
  synthetic-calendar confirmation. An injected publication HTTP 503 is retried;
  durable simulator publication converges; disconnect preserves remote events
  when requested.

Earlier focused raw runs and screenshots are retained in `raw/`. The initial
adaptation browser failure exposed an in-progress development-schema mismatch;
forward migration 0010 repairs that state. A subsequent locator failure was
corrected to identify the task selector by its accessible role. These are not
provider production failures and are not concealed by the final passing run.

The calendar screenshot was visually inspected: no overlapping controls or
clipped content at desktop width. Synthetic test accounts retain accumulated
examples, which makes this development screenshot longer than a fresh workspace.
R1 contains the prior fresh-source mobile check; R4 will repeat clean setup for
the integrated release. This report does not claim independent human usability
testing, live-provider reliability or the unexecuted R2 human/live-AI gates.
