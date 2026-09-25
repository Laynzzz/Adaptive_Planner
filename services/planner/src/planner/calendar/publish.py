"""Durable per-calendar serialization and read-before-retry remote publication.

An HTTP request already in flight cannot be fenced remotely. Every outcome stays
on its operation; obsolete writes are reconciled by a subsequent current pass.
"""

from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.calendar.provider import ProviderError
from planner.calendar.reconcile import canonical, conflict, event_id, owned, payload_for
from planner.calendar.sync import _effective
from planner.db.calendar_models import BlockEventMapping, CalendarConnection, CalendarWriteOperation
from planner.db.job_models import ProposalBlock, ProposalRecord, PublicationOperation
from planner.db.models import AuditEvent, PlanningState, Task
from planner.jobs.coalescing import enqueue_in_transaction
from planner.observability.runtime import traced_owner_work


@dataclass(frozen=True)
class PublicationResult:
    state: str
    published: int = 0
    pending: int = 0
    conflicts: int = 0


def _guard(engine, owner, proposal, token, clock):
    with Session(engine) as db, db.begin():
        connection = db.scalar(
            select(CalendarConnection).where(CalendarConnection.owner_id == owner).with_for_update()
        )
        state = db.get(PlanningState, owner)
        if (
            connection.state != "CONNECTED"
            or connection.lease_token != token
            or connection.lease_until <= clock()
            or state.active_proposal_id != proposal
        ):
            return False
        connection.lease_until = clock() + timedelta(seconds=30)
        return True


def _prepare(db, owner, proposal_id, connection, now):
    blocks = {
        b.id: b
        for b in db.scalars(
            select(ProposalBlock).where(
                ProposalBlock.owner_id == owner, ProposalBlock.proposal_id == proposal_id
            )
        )
    }
    mappings = {
        m.block_id: m
        for m in db.scalars(select(BlockEventMapping).where(BlockEventMapping.owner_id == owner))
    }
    for block_id in blocks.keys() | mappings.keys():
        mapping = mappings.get(block_id)
        if mapping and (mapping.state in ("CONFLICT", "IGNORED") or mapping.commitment):
            continue
        block = blocks.get(block_id)
        if not mapping:
            mapping = BlockEventMapping(
                owner_id=owner,
                block_id=block_id,
                task_id=block.task_id,
                event_id=event_id(owner, connection.calendar_id, block_id),
            )
            db.add(mapping)
            db.flush()
        action = "UPSERT" if block else "DELETE"
        operation = db.scalar(
            select(CalendarWriteOperation).where(
                CalendarWriteOperation.owner_id == owner,
                CalendarWriteOperation.proposal_id == proposal_id,
                CalendarWriteOperation.block_id == block_id,
                CalendarWriteOperation.action == action,
            )
        )
        if operation:
            continue
        desired = (
            payload_for(owner, connection.calendar_id, block, db.get(Task, block.task_id).title)
            if block
            else None
        )
        operation = CalendarWriteOperation(
            id=uuid4(),
            owner_id=owner,
            proposal_id=proposal_id,
            block_id=block_id,
            action=action,
            desired_payload=desired,
            updated_at=now,
        )
        db.add(operation)
    db.flush()


def _record(engine, operation_id, token, clock, *, remote=None, failure=None, reason=None):
    with Session(engine) as db, db.begin():
        operation = db.get(CalendarWriteOperation, operation_id)
        state = db.scalar(
            select(PlanningState)
            .where(PlanningState.owner_id == operation.owner_id)
            .with_for_update()
        )
        connection = db.scalar(
            select(CalendarConnection)
            .where(CalendarConnection.owner_id == operation.owner_id)
            .with_for_update()
        )
        mapping = db.get(BlockEventMapping, (operation.owner_id, operation.block_id))
        operation.updated_at = clock()
        if remote:
            operation.observed_payload, operation.observed_etag = remote.payload, remote.etag
        if (
            state.active_proposal_id != operation.proposal_id
            or connection.lease_token != token
            or connection.state != "CONNECTED"
        ):
            operation.state = "OBSOLETE"
            operation.reason = reason or failure
            return
        if failure == "CONFLICT":
            before = _effective(db, operation.owner_id)
            conflict(
                db, mapping, reason or "MANUAL_EDIT", remote.payload if remote else None, clock()
            )
            db.flush()
            if before != _effective(db, operation.owner_id):
                state.revision += 1
                state.calendar_revision += 1
                db.add(
                    AuditEvent(
                        owner_id=operation.owner_id,
                        operation="calendar.conflict",
                        revision=state.revision,
                    )
                )
                enqueue_in_transaction(db, operation.owner_id, now=clock())
            operation.state = "CONFLICT"
        elif failure:
            operation.state = "UNCERTAIN" if failure == "AMBIGUOUS_WRITE" else "RETRYABLE"
            if failure in ("PERMANENT_VALIDATION", "AUTHENTICATION_REQUIRED"):
                operation.state = "FAILED"
            operation.reason = failure
            connection.last_error = failure
            if failure == "AUTHENTICATION_REQUIRED":
                connection.state = "NEEDS_REAUTH"
        else:
            operation.state, operation.reason = "DONE", None
            mapping.state = "DELETED" if operation.action == "DELETE" else "PUBLISHED"
            if remote:
                mapping.etag, mapping.published_payload = remote.etag, remote.payload
            mapping.operation_id = operation.id
            intent = db.scalar(
                select(PublicationOperation).where(
                    PublicationOperation.owner_id == operation.owner_id,
                    PublicationOperation.proposal_id == operation.proposal_id,
                    PublicationOperation.block_id == operation.block_id,
                )
            )
            if intent:
                intent.state = "PUBLISHED"


def _run_operation(engine, operation_id, provider, token, clock):
    with Session(engine) as db, db.begin():
        operation = db.get(CalendarWriteOperation, operation_id)
        owner, proposal = operation.owner_id, operation.proposal_id
        mapping = db.get(BlockEventMapping, (owner, operation.block_id))
        connection = db.get(CalendarConnection, owner)
        calendar_id, remote_id = connection.calendar_id, mapping.event_id
        old, desired, action, block_id = (
            mapping.published_payload,
            operation.desired_payload,
            operation.action,
            mapping.block_id,
        )
        baseline_etag = mapping.etag
        recovering_uncertain_write = operation.state == "UNCERTAIN"
        known_writes = [
            (o.observed_etag, canonical(o.observed_payload))
            for o in db.scalars(
                select(CalendarWriteOperation).where(
                    CalendarWriteOperation.owner_id == owner,
                    CalendarWriteOperation.block_id == block_id,
                    CalendarWriteOperation.observed_payload.is_not(None),
                    CalendarWriteOperation.state.in_(["DONE", "OBSOLETE"]),
                    CalendarWriteOperation.reason.is_(None),
                )
            )
        ]
        operation.attempts += 1
        # Persist uncertainty before the call so a process crash is recoverable.
        operation.state, operation.updated_at = "UNCERTAIN", clock()
    remote = None
    try:
        if not _guard(engine, owner, proposal, token, clock):
            return
        try:
            remote = provider.get_event(calendar_id, remote_id)
        except ProviderError as error:
            if error.kind != "NOT_FOUND":
                raise
        if remote and not owned(remote.payload, owner, block_id):
            _record(
                engine,
                operation_id,
                token,
                clock,
                remote=remote,
                failure="CONFLICT",
                reason="OWNERSHIP_MISMATCH",
            )
            return
        if remote is None and old and action != "DELETE":
            _record(
                engine, operation_id, token, clock, failure="CONFLICT", reason="MANUAL_DELETION"
            )
            return
        if (
            remote
            and recovering_uncertain_write
            and canonical(remote.payload) == canonical(desired)
        ):
            _record(engine, operation_id, token, clock, remote=remote)
            return
        if (
            remote
            and old
            and remote.etag != baseline_etag
            and (remote.etag, canonical(remote.payload)) not in known_writes
        ):
            _record(
                engine,
                operation_id,
                token,
                clock,
                remote=remote,
                failure="CONFLICT",
                reason="MANUAL_EDIT",
            )
            return
        if (
            remote
            and canonical(remote.payload) != canonical(old)
            and canonical(remote.payload) != canonical(desired)
        ):
            if (remote.etag, canonical(remote.payload)) not in known_writes:
                _record(
                    engine,
                    operation_id,
                    token,
                    clock,
                    remote=remote,
                    failure="CONFLICT",
                    reason="MANUAL_EDIT",
                )
                return
        if action == "DELETE":
            if remote:
                if not _guard(engine, owner, proposal, token, clock):
                    return
                provider.delete_event(calendar_id, remote_id, etag=remote.etag)
            _record(engine, operation_id, token, clock)
            return
        if remote and canonical(remote.payload) == canonical(desired):
            _record(engine, operation_id, token, clock, remote=remote)
            return
        if not _guard(engine, owner, proposal, token, clock):
            return
        result = (
            provider.update_event(calendar_id, remote_id, desired, etag=remote.etag)
            if remote
            else provider.create_event(calendar_id, desired)
        )
        _record(engine, operation_id, token, clock, remote=result.event)
    except ProviderError as error:
        if error.kind == "CONFLICT" and _guard(engine, owner, proposal, token, clock):
            # A failed If-Match invalidates the earlier read. Reserve the actual
            # current remote interval, never the interval from before the race.
            try:
                current = provider.get_event(calendar_id, remote_id)
            except ProviderError as refresh_error:
                if refresh_error.kind == "NOT_FOUND":
                    _record(
                        engine,
                        operation_id,
                        token,
                        clock,
                        failure="CONFLICT",
                        reason="MANUAL_DELETION",
                    )
                else:
                    _record(engine, operation_id, token, clock, failure=refresh_error.kind)
                return
            reason = (
                "MANUAL_EDIT" if owned(current.payload, owner, block_id) else "OWNERSHIP_MISMATCH"
            )
            _record(
                engine,
                operation_id,
                token,
                clock,
                remote=current,
                failure="CONFLICT",
                reason=reason,
            )
            return
        _record(engine, operation_id, token, clock, remote=remote, failure=error.kind)


@traced_owner_work("publish")
def publish_active(engine, owner_id, provider, *, clock, limit=200) -> PublicationResult:
    token = uuid4()
    with Session(engine) as db, db.begin():
        state = db.scalar(
            select(PlanningState).where(PlanningState.owner_id == owner_id).with_for_update()
        )
        connection = db.scalar(
            select(CalendarConnection)
            .where(CalendarConnection.owner_id == owner_id)
            .with_for_update()
        )
        if not connection or connection.state != "CONNECTED":
            return PublicationResult(connection.state if connection else "DISCONNECTED")
        if connection.lease_until and connection.lease_until > clock():
            return PublicationResult("BUSY")
        if not state.active_proposal_id:
            return PublicationResult("NO_ACTIVE_PLAN")
        proposal_id = state.active_proposal_id
        connection.lease_token, connection.lease_until = token, clock() + timedelta(seconds=30)
        _prepare(db, owner_id, proposal_id, connection, clock())
        operations = list(
            db.scalars(
                select(CalendarWriteOperation.id)
                .where(
                    CalendarWriteOperation.owner_id == owner_id,
                    CalendarWriteOperation.proposal_id == proposal_id,
                    CalendarWriteOperation.state.in_(
                        ["PENDING", "UNCERTAIN", "RETRYABLE", "OBSOLETE"]
                    ),
                )
                .order_by(CalendarWriteOperation.id)
                .limit(limit)
            )
        )
    try:
        for operation_id in operations:
            if not _guard(engine, owner_id, proposal_id, token, clock):
                break
            _run_operation(engine, operation_id, provider, token, clock)
    finally:
        with Session(engine) as db, db.begin():
            connection = db.scalar(
                select(CalendarConnection)
                .where(CalendarConnection.owner_id == owner_id)
                .with_for_update()
            )
            if connection.lease_token == token:
                connection.lease_until, connection.lease_token = None, None
    with Session(engine) as db, db.begin():
        connection = db.get(CalendarConnection, owner_id)
        rows = list(
            db.scalars(
                select(CalendarWriteOperation).where(
                    CalendarWriteOperation.owner_id == owner_id,
                    CalendarWriteOperation.proposal_id == proposal_id,
                )
            )
        )
        conflicts = len(
            list(
                db.scalars(
                    select(BlockEventMapping).where(
                        BlockEventMapping.owner_id == owner_id,
                        BlockEventMapping.state == "CONFLICT",
                    )
                )
            )
        )
        published = sum(o.state == "DONE" for o in rows)
        pending = len(rows) - published
        current = db.get(PlanningState, owner_id).active_proposal_id == proposal_id
        status = (
            "NEEDS_REAUTH"
            if connection.state == "NEEDS_REAUTH"
            else "CONFLICT"
            if conflicts
            else "PARTIAL"
            if pending or not current
            else "PUBLISHED"
        )
        db.get(ProposalRecord, proposal_id).publication_state = status
        return PublicationResult(status, published, pending, conflicts)
