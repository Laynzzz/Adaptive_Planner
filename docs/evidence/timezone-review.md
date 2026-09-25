# Independent timezone-change review

2026-09-25. Read-only review of `domain/timezone_change.py`, `api/preferences.py`, the shared command transaction, `TimezoneSettings.tsx`, and the current integration/UI tests. Review scope: owner isolation, revision-bound confirmation, absolute versus civil time semantics, DST resolution, malformed input, atomic rollback and stale previews.

No confirmed important correctness defect was found in the reviewed code. Preview reads use one repeatable-read transaction. The digest includes owner, revision, source/target zones and displayed date boundaries. Confirmation recomputes under the same owner lock used by input mutations. Timestamp deadlines, releases, fixed events and existing availability become explicit UTC instants before the identity zone changes; date-only deadlines retain dates. A new weekly-rule conflict aborts the transaction. API errors and stale revisions leave the form recoverable.

Independent command: `.venv/Scripts/python.exe -m pytest tests/integration/test_timezone_settings.py -q`. Result: **4 passed in 2.47s**. Cases cover cross-owner preview misuse, required confirmation, stale digest, weekday-conflict rollback, DST date boundary, timestamp/release/availability preservation, idempotent replay and invalid timezone.

Optional UI robustness observation sent to the implementation owner: while a preview request is in flight the timezone text input remains editable. A late response can display the previous target beneath a newly edited input. The preview heading and submitted command remain consistent with each other, so this does not silently apply the new unreviewed target. Disabling the input while busy or discarding an outdated request response would remove the confusing intermediate state. No feature edits were made during the concurrent demo capture.

Limits: this review is scoped evidence, not an exhaustive proof over the IANA timezone database. Production identity/session and live provider verification remain separate gates.
