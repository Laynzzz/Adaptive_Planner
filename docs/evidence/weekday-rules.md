# Reviewed weekday rules

Date: 2026-09-25. This finishes the authorized weekday-rule path from Task 9 without changing frozen extraction schemas, provider output, metrics, or InputSnapshot.

Persisted owner-scoped rules distinguish SOFT_AVOID, HARD_UNAVAILABLE and HARD_NO_DEADLINE, with Monday 0 through Sunday 6. API GET/POST/DELETE `/api/v1/weekday-rules` uses coherent reads, revision checks, CSRF and idempotent command receipts. Soft avoidance expands to preferred complementary local days without removing availability. Hard unavailability adds local full-day busy intervals. Actual UTC boundaries preserve 23/25-hour DST days. At least one preferred weekday must remain when adding soft avoidance.

Date-only deadline rules apply to the entered calendar day, not its next-midnight exclusive bound; timestamp rules use the owner's local timezone. Task create/patch, what-if preview/apply and reviewed AI acceptance share deadline validation. Adding a conflicting deadline restriction, or making protected work unavailable, rejects atomically rather than storing an invalid snapshot. Historical DONE/CANCELLED task deadlines do not block rule creation; reopening through a correction is revalidated.

AI acceptance integration is owned by the backend agent: selected constraint keys require confirmation paths `constraints.<key>`; rule-only acceptance is allowed; combined task/rule changes roll back together on conflict. Unselected proposed rules remain unapplied. Frozen provider/schema/evaluation files were not changed by this increment.

Initial red run: three HTTP 404 failures for missing rule routes and one missing expansion function. Final focused command:

```powershell
.\.tools\bin\uv.exe run pytest tests/integration/test_weekday_rules.py tests/integration/test_accept_interpretation.py tests/integration/test_adaptation.py -q --tb=short
```

**36 passed in 18.56s**, [raw result](raw/weekday-rules-green.txt). Scoped Ruff passed. Tests cover owner isolation, deletion, hard/soft distinction, DST, date-only and owner-local timestamp semantics, existing/new deadline conflict, what-if rejection and protected-work rollback, plus AI and adaptation regressions. Root owns browser evidence.

Owned files: `db/weekday_models.py`, `domain/weekday_rules.py`, `api/weekday_rules.py`, `tests/integration/test_weekday_rules.py`, migration `0013_weekday_rules` down `0012_calendar_owned_operation`, the weekday import in migration metadata, task-validation hook in `api/routes.py`, snapshot hook in `jobs/dispatcher.py`, and app router registration. No staging or commits by this agent.
