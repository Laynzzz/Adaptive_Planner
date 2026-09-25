# Independent R2 backend review

Date: 2026-09-25. Reviewer: domain/contracts agent, separate from AI and calendar implementation owners. Scope: Tasks 9–12 acceptance, spend accounting, worker fencing, calendar mirror/publication, OAuth ownership and manual-change recovery. This was a read-only code review with disposable-database reproductions; the reviewer changed only this report.

## Findings

1. **P1 — publication-discovered commitments did not revision scheduling inputs.** `calendar/publish.py::_record` called `reconcile.conflict`, changing a mapping into protected work, without incrementing planning/calendar revisions or creating replan demand. Real PostgreSQL reproduction: activate/publish/sync at revision 0; move the remote block from 09:00–10:00 to 11:00–12:00; activate another version and publish. Result was CONFLICT with one protected commitment, revision 0 and no PendingReplan. A subsequent sync returned `changed=False`, leaving the inconsistency permanent. Reported to calendar owner; owner added effective-input comparison under the owner lock plus revision, audit and enqueue. Regression: `test_publication_discovered_move_revisions_inputs_and_enqueues_replan`.

2. **P1 — stale authentication failure could cancel a newer disconnect.** `calendar/sync.py::synchronize` fenced successful generation publication but its error handler unconditionally changed the connection to NEEDS_REAUTH. A controlled provider callback applied DISCONNECTING and incremented generation before returning AUTHENTICATION_REQUIRED. The old sync overwrote the newer command with NEEDS_REAUTH, which the disconnect worker would no longer claim. Reported to owner; sync failure now checks current state/calendar/generation, and worker auth outcome checks request identity/state. Regression: `test_stale_sync_auth_failure_cannot_overwrite_disconnect`, plus the calendar owner's worker regression.

3. **P1 — uncertain successful updates were mistaken for manual edits.** `calendar/publish.py::_run_operation` checked a changed ETag before recognizing that the remote payload exactly matched the desired payload of an uncertain operation. Real PostgreSQL/FakeCalendar reproduction: initial publish; revised selected title; timeout after successful remote update. First pass was PARTIAL with two total remote writes; retry returned CONFLICT/MANUAL_EDIT with no additional write. Owner added exact desired owned-state reconciliation for a previously UNCERTAIN operation while retaining normal manual-edit checks. Regression: `test_timeout_after_remote_update_reconciles_own_changed_etag`.

4. **P1 — conditional-write conflict stored the stale prewrite interval.** A manual move between GET and conditional update correctly prevented overwrite, but the ProviderError handler passed the old GET payload into `_record`. Real PostgreSQL reproduction moved the remote event to 11:00–12:00 immediately before If-Match rejection; stored protected commitment remained 09:00–10:00. A terminal CONFLICT could then leave the solver reserving the wrong time until a later explicit sync. The calendar owner added a guarded reread after conditional conflict, records the fresh payload/ETag or deletion, and preserves retryability if that reread fails. Its expanded existing conditional-race regression now checks the actual 11:00 commitment.

5. **P1 — off-grid manual moves crashed snapshot capture.** A published event manually moved to 11:07–12:07 synced successfully but then `capture_snapshot` raised `ValueError: LOCK_NOT_GRID_ALIGNED`; this could escape the dispatcher and stop a worker. The owner added an internal calendar-only off-grid path that preserves the exact remote interval and explicit rounding diagnostics. The resulting snapshot reports `CALENDAR_OFF_GRID`, yielding a durable failed solve rather than treating rounded work as completed or moving the remote event. Manual user locks still reject off-grid times. Calendar and domain regression coverage was added by the owner.

All five reproductions used the repository's fresh migrated PostgreSQL fixture, selected immutable proposals and synthetic provider; no live provider was contacted. No implementation changes were made by the reviewer during the review. The parent subsequently assigned weekday-rule implementation as a separate increment.

## Boundaries inspected

- AI interpretation creation takes the owner planning-state lock and permits one active interpretation per owner. Provider work is outside HTTP requests, globally claimed into the configured interpretation pool, and fenced on completion. Output alone cannot create tasks.
- AI acceptance revalidates schema/source spans/dependency cycles, requires selected unknown overrides and inferred confirmations, checks the original planning revision and applies one transactional command. Unsupported weekday constraints fail explicitly rather than being silently accepted.
- Paid model invocation requires explicit configured approval/budget/prices. Reservation is serialized and conservative, occurs before invocation, and uncertain spend remains charged rather than released optimistically. No paid call was made during review.
- Evaluation code keeps failed parses in reference denominators and reports raw counts. Frozen mock evidence explicitly does not establish live-model quality or independent human annotation quality.
- Calendar OAuth is separate from login, uses browser-session-bound expiring PKCE state, encrypts refresh tokens and rejects superseded authorization callbacks. Endpoint ownership and mutation CSRF dependencies were inspected.
- Mirror sync stages pages and commits complete generations under owner and calendar locks; incomplete pages preserve the old cursor/mirror. Publication uses stable provider IDs, ownership markers, conditional ETags, durable operation state and active-selection fencing. The findings above concern uncovered branches in those mechanisms.

## Verification

Focused command (run after owner corrections):

```powershell
.\.tools\bin\uv.exe run pytest tests/unit/test_interpretation.py tests/integration/test_accept_interpretation.py tests/unit/test_eval_metrics.py tests/unit/test_calendar_provider.py tests/unit/test_ics.py tests/integration/test_calendar_sync.py tests/fault/test_calendar_publication.py -q --tb=short
```

An intermediate run observed 53 passing tests and the owner's newly added stale-auth regression failing before its fix loaded. Fresh verification after findings 1–3 corrections: **55 passed in 17.72s**. Additional real-database authorization/command checks (`tests/integration/test_calendar_oauth.py tests/integration/test_calendar_commands.py`): **11 passed in 4.00s**. Final affected calendar publication/sync/command rerun after findings 4–5 corrections: **24 passed in 13.39s**. No reproduced runtime finding remains open in this review. Browser verification and live Google/model capability gates remain separate evidence owned by root.
