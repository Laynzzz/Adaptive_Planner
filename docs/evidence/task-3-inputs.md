# Task 3: OIDC, ownership, and transactional input evidence

Date: 2026-09-25. Local Windows/Python 3.12.14, PostgreSQL 17.9 Docker, Keycloak 26.6.2 fixture; two synthetic users only. Revision: the commit introducing this report. This is a local functional/authentication result, not a universal security or production-readiness claim.

## Implemented contracts

- Real authorization-code OIDC with state, nonce, and S256 PKCE. Authlib/Jose verifies RS256 signature, issuer, audience, nonce, required claims and expiry. Identity is unique by issuer plus subject. The application does not store passwords or expose provider tokens to the browser.
- Opaque browser tokens are hashed in PostgreSQL. Session expiry and logout are checked server-side; mutations require the session CSRF token and reject an unexpected Origin. Cookies are HttpOnly/SameSite=Lax, Secure outside the explicitly local environment. API responses use no-store. CLI access logging is disabled to avoid logging callback authorization codes; SQL bound parameters are hidden.
- Tasks, dependency edges, availability and fixed events are owner scoped. Dependency foreign keys include owner and task ID. A database trigger rejects update/delete of audit rows; privileged administrators remain outside that protection claim.
- A NOWAIT row lock on user_planning_state serializes each owner's commands. Mutation, revision increment, audit row, seven-day receipt and durable coalesced PendingReplan update commit together. Equal key/body replays the original response after current session authorization; changed body/key and stale revisions return 409. Lock contention returns retryable COMMAND_IN_PROGRESS. Receipt expiry does not relax revision checks.
- Input GET handlers use one PostgreSQL REPEATABLE READ snapshot so payloads cannot be paired with a later revision. Task pagination orders by created_at/id, binds owner/state filters, and fixes an upper watermark. Separate page requests do not promise an unchanged snapshot across edits or deletes.
- Public request/response models support generated OpenAPI clients. Typed input validation preserves entered deadlines and rejects invalid intervals, timezone IDs, block settings and effort outside the PostgreSQL integer range.
- `seed-demo` is local-fixture-only and requires both demo identities to have completed real sign-in. It creates two deterministic-ID synthetic tasks per identity, tomorrow's UTC window if no availability exists, and a revisioned demand for planning. Reruns preserve existing demo tasks even after receipts expire. No invented OIDC subject is seeded.

## Test-first and verification record

Commands use `uv` from repository root (this host invoked `.\.tools\bin\uv.exe`).

- Initial anonymous/callback tests: 404 instead of 401/400. Real-provider login fixture also stopped on missing login route (404 instead of redirect). After implementing routes, `pytest ...test_isolation.py -k 'provider or callback'`: 2 passed. No authentication dependency override, fabricated session, or password-grant shortcut was used.
- Initial command persistence/replay tests: 2 failed on missing task route (404 instead of 201). After transaction implementation: 9 command/isolation tests passed, then 19 with ownership, FK, CSRF, origin, audit, receipt-expiry, pagination and dependency coverage.
- `seed-demo` first failed with explicit not-implemented exit 2. Its CLI test now runs the real subprocess twice, checks both users receive exactly two tasks and verifies revision remains 1 after replay.
- Negative-input regressions first reproduced missing no-store and uncaught ZoneInfoNotFoundError. A review also reproduced integer overflow for 3,000,000,000 minutes and malformed-cursor IndexError. These now return client errors and leave revisions unchanged.
- Concurrent-read regression first returned old availability with new revision 2. A real second PostgreSQL connection commits new windows/revision between the handler's reads. After the isolation fix, the response is old windows/revision 1; replaying it gets 409 and the newer window remains. This is a controlled interleaving on real PostgreSQL, not a mocked transaction.
- Final targeted command: `uv run pytest tests/unit/test_auth_tokens.py tests/integration/test_bootstrap.py tests/integration/test_commands.py tests/integration/test_isolation.py -q`: **40 passed in 23.30s**. Includes six signed-token negative controls for issuer/audience/nonce/expiry/subject/signature, eight bootstrap checks, and 26 auth/input checks.
- `uv sync --frozen --all-extras`: **Checked 58 packages**, exit 0. Authlib 1.8 uses httpx2; httpx2 2.13.1 and directly used joserfc 1.7.5 are now exact dependencies. HTTPX remains the FastAPI TestClient dependency.
- Scoped Ruff check on Task 3 modules/tests/migration: passed after import/format fixes. FastAPI Depends is explicitly configured as a declarative safe default for Ruff B008; no test/runtime warning filters were added.

## Test fixture and migration details

Every integration case migrates a fresh randomly named PostgreSQL database. `api_a` and `api_b` submit the real Keycloak login form, follow the real authorization-code callback, obtain the API's real session and CSRF token, and then use normal authorization. Python CookieJar does not implement browsers' trusted-loopback cookie behavior; only the local provider test transport clears its Secure cookie flag for HTTP loopback. This does not change production cookies, signature verification, middleware, or session handling. Separate real-browser evidence belongs to the frontend report.

`valid_task_command()` uses fixed 2026-09-25 17:00 UTC intent, 60 minutes, revision zero and a fresh idempotency key. The authenticated wrapper moves that key into Idempotency-Key and retains CSRF/session validation. Tests that deliberately omit headers use its raw client.

Migration e3b311ba42f4 follows bootstrap and creates explicit relational tables/constraints plus the append-only audit trigger. During development, its pending/state columns were finalized after an exploratory local upgrade; the local application DB received matching additive ALTERs and trigger creation, with no records deleted. Fresh isolated databases always exercised the final migration sequence. Task 6 adds proposal/queue tables and the owner-inclusive active-proposal foreign key separately.

## Remaining limits and reproduction

Start Compose, run migrations, run the API and frontend, sign in once as each local demo account, then run `uv run python -m planner.cli seed-demo`. Run the targeted command above while PostgreSQL and Keycloak are running. Provider failures fail tests rather than skip them.

Session revocation is local logout/expiry; provider global logout, refresh-token workflows and production deployment are not implemented here. Availability remains explicit dated windows with UTC workspace preference in this slice; timezone changes require the later explicit preview contract. Work logs, locks and adaptation are dependent tasks. Local identity fixtures and seed passwords must never be used for hosted production. The queue handoff is durable demand, not a claim that Task 3 alone runs jobs. N+1 task dependency reads remain a baseline for the mandated SQL study; no performance improvement is claimed.

References: [Authlib OIDC clients](https://docs.authlib.org/en/stable/oauth2/client/http/index.html), [Keycloak OIDC flow](https://www.keycloak.org/securing-apps/oidc-layers). Native installed-library behavior and the real local-provider tests above establish the verified version combination.
