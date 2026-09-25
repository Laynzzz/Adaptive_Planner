# ADR 0002: Durable calendar generations and recoverable publication

Status: implemented locally; live Google journey remains unexecuted.

Local activation is a database transaction. Google event writes cannot join that
transaction, so the UI reports activation and publication separately. Each block
gets a deterministic SHA-256 hexadecimal event ID derived from owner, selected
calendar, and stable block ID. A stored mapping and matching private app/owner/block
markers are both required before modifying an existing remote event.

Full and incremental imports stage every page in PostgreSQL under a generation.
Only the final page's sync token can become current, together with the completed
mirror. A failed page leaves the previous cursor and mirror visible. Invalid tokens
start a full generation rather than deleting application tasks or history. Both
successful and failed completions are fenced by calendar identity, connection state,
and generation. Busy intervals are unioned before comparison; no-op imports do not
cause revision churn. Recognized active app events are excluded from imported busy.

Publication operations are committed before provider calls. A per-connection lease
serializes writers, and every new request rechecks the active proposal. Recovery
reads the deterministic ID first. An uncertain operation whose owned remote payload
matches its desired payload is complete, including updates whose ETag changed.
Other edits are conflicts. Conditional writes use the observed ETag; after a failed
condition the worker rereads the resource before recording its actual interval.
An already in-flight HTTP call cannot be fenced by a database lease. Its observed
outcome stays attached to the old operation and is reconciled toward the current
plan on a subsequent pass, without treating manually changed ETags as app writes.

Manual moves become explicit protected commitments, revisioned and audited whether
discovered by import or publication. Manual deletion is a conflict, not a create
retry. User resolutions are revisioned commands. An off-grid remote commitment
retains its exact original interval in the mirror/conflict and is conservatively
reserved on the planning grid. It carries `CALENDAR_OFF_GRID`, which prevents a
valid candidate until the user restores or removes that commitment; rounded extra
minutes are never silently counted as work. Local manual lock entry remains strict.

Google authorization is separate from login: expiring state is bound to the browser
session and owner, PKCE binds the exchange, and refresh tokens use Fernet encryption
with an environment key. Refresh authentication errors become NEEDS_REAUTH. Disconnect
immediately blocks new publication, explicitly records whether remote app events
should remain, and removes credentials after attempted revocation. Failed revocation
is visible as REVOCATION_UNCONFIRMED. Cleanup never deletes a mismatched or manually
edited event merely because its ID matches a mapping.

The local deployment reserves two threads for calendar I/O and two for AI I/O, for
four configured I/O workers total, separate from two solver subprocess slots.
These reservations prevent calendar traffic from consuming the AI partition.
This is a single-process-per-service configuration bound, not a claim of a global
cross-host limit. Calendar claims use durable expiring owner leases; provider HTTP
requests have ten-second transport timeouts. Publication passes cap operation count
at 200, preserving remaining durable work for later passes.

The simulator stores synthetic remote state in the owner-scoped database connection
record, so local API/worker restarts do not erase the fake remote calendar. Fault tests
use an injectable in-memory provider to place failures at precise boundaries. Neither
mode proves Google's real authorization, recurrence expansion or write behavior.

Alternatives rejected: advancing cursors page by page exposes incomplete capacity;
retrying POST blindly duplicates uncertain writes; unconditional updates overwrite
manual edits; claiming remote atomicity hides unavoidable HTTP races.

Provider references: [incremental synchronization](https://developers.google.com/workspace/calendar/api/guides/sync),
[conditional modification](https://developers.google.com/workspace/calendar/api/guides/version-resources),
[event resource semantics](https://developers.google.com/workspace/calendar/api/v3/reference/events).
